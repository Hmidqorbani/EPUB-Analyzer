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

import main

PREFERRED_PORT = 48731


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
    if port != PREFERRED_PORT:
        # پورت ثابت اشغال است؛ LocalStorage قبلی (تم/زبان) از دست می‌رود.
        print(f"[EPUB Analyzer] پورت {PREFERRED_PORT} اشغال است؛ از پورت {port} استفاده می‌شود.")
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_config=None))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    webview.create_window("EPUB Analyzer", f"http://127.0.0.1:{port}",
                          width=1180, height=860, min_size=(480, 600))
    webview.start(private_mode=False,
                  storage_path=os.path.join(os.environ.get("APPDATA", "."), "EPUBAnalyzer"))
    server.should_exit = True