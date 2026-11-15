"""EPUB Analyzer: اجرای دسکتاپی (سرور FastAPI داخلی + پنجره WebView).

نصب:  pip install pywebview pyinstaller
اجرا:  python gui.py
"""
import os
import socket
import threading
import time

import uvicorn
import webview

import main  # همان main.py پروژه؛ بدون تغییر

PREFERRED_PORT = 48731  # پورت ثابت تا LocalStorage (تم انتخاب‌شده) بین اجراها حفظ شود


def pick_port() -> int:
    for port in (PREFERRED_PORT, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("پورت آزاد پیدا نشد.")


if __name__ == "__main__":
    port = pick_port()
    # log_config=None ضروری است: در حالت --windowed مقدار sys.stdout برابر None است و لاگ پیش‌فرض uvicorn کرش می‌کند
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_config=None))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    webview.create_window("EPUB Analyzer", f"http://127.0.0.1:{port}", width=1180, height=860, min_size=(480, 600))
    webview.start(private_mode=False,
                  storage_path=os.path.join(os.environ.get("APPDATA", "."), "EPUBAnalyzer"))
    server.should_exit = True
