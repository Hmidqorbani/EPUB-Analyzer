
<div align="center">

<img src="docs/icon.ico" alt="EPUB Analyzer logo" width="128">

# EPUB Analyzer

**Count the words, letters, sentences and chapters of any book (EPUB, TXT, DOCX, PDF, FB2).**
<br>
**کلمه‌ها، حرف‌ها، جمله‌ها و فصل‌های هر کتاب (EPUB، TXT، DOCX، PDF، FB2) را بشمارید.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Web%20%7C%20Windows-0f766e)
![Version](https://img.shields.io/badge/version-1.1.1-informational)

[English](#english) · [فارسی](#فارسی)

</div>

## Screenshots · تصاویر

<p align="center">
  <img src="docs/img-1.png" alt="Light theme" width="48%">
  <img src="docs/img-2.png" alt="Dark theme" width="48%">
</p>

<p align="center">
  <img src="docs/img-3.png" alt="Light theme" width="96%">
</p>
<p align="center">
  <img src="docs/img-4.png" alt="Light theme" width="96%">
</p>
<p align="center">
  <img src="docs/img-5.png" alt="Light theme" width="96%">
</p>
<p align="center">
  <img src="docs/img-6.png" alt="Light theme" width="96%">
</p>

---

<a id="فارسی"></a>
<br>
<br>
<br>
<br>
<div dir="rtl">

## معرفی

### EPUB Analyzer
ابزاری سبک است که فایل کتاب را کاملاً در حافظه می‌خواند و آمار دقیق متن آن را نشان می‌دهد: کلمه، حرف، کاراکتر، پاراگراف، جمله، فصل، آمار هر فصل، متادیتا، جلد، زبان تشخیص‌داده‌شده، زمان مطالعه (کل و هر فصل) و تعداد صفحات تخمینی. فرمت‌های پشتیبانی‌شده: **EPUB، TXT، DOCX، PDF، FB2**. فارسی، عربی، انگلیسی و زبان‌های لاتین پشتیبانی می‌شوند. کل برنامه (Backend با FastAPI و Frontend با HTML/CSS/JS) در یک فایل `main.py` است و می‌توان آن را به‌صورت اپ دسکتاپ ویندوز هم بسته‌بندی کرد.

## ویژگی‌ها

- **پنج فرمت کتاب:** EPUB، TXT، DOCX، PDF، FB2
- **رابط دوزبانه (فارسی/انگلیسی)** با تشخیص خودکار زبان مرورگر و ذخیره در LocalStorage
- آپلود با Drag & Drop یا انتخاب فایل، همراه با نمایش نام، حجم، پسوند و وضعیت پردازش
- **نمایش جلد کتاب** برای فایل‌های EPUB (با سه روش تشخیص)
- **تشخیص خودکار زبان محتوا** (فارسی، عربی، انگلیسی، روسی، چینی) بر اساس اسکریپت غالب
- اعتبارسنجی ساختار داخلی EPUB (ZIP، `container.xml`، mimetype، DRM/رمزگذاری، ZIP Bomb، مسیرهای مخرب)
- پردازش فقط در حافظه؛ هیچ فایلی روی دیسک ذخیره نمی‌شود
- Navigation، فهرست مطالب، جلد و صفحه‌های تکراری در شمارش‌ها لحاظ نمی‌شوند
- متادیتا: عنوان، نویسنده، ناشر، زبان، شناسه، تاریخ انتشار، توضیحات
- آمار تکمیلی: میانگین طول کلمه، جمله و پاراگراف، زمان مطالعه (پیش‌فرض ۲۰۰ کلمه در دقیقه) و تعداد صفحات تخمینی (پیش‌فرض ۳۰۰ کلمه در صفحه) که هر دو در رابط کاربری قابل تغییرند
- **زمان مطالعه به‌تفکیک هر فصل**
- **فصل‌بندی دقیق‌تر:** تقسیم فایل‌های چندفصلی بر اساس Anchorهای TOC و در نبود TOC بر اساس تیترهای داخل فایل
- جدول Responsive آمار فصل‌ها با قابلیت مرتب‌سازی
- تم روشن و تیره (ذخیره در LocalStorage)
- مستندات Swagger در `/docs`

## ساختار پروژه

```text
epub-analyzer/
├── main.py            # Backend + Frontend (FastAPI)
├── gui.py             # اپ دسکتاپ ویندوز (pywebview)
├── installer.iss      # اسکریپت Inno Setup
├── icon.ico           # آیکون برنامه
├── requirements.txt
├── README.md
└── docs/              # لوگو و تصاویر
```

## اجرای سریع (وب)

نیاز به Python 3.11 یا بالاتر.

**ویندوز (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**لینوکس / مک**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

آدرس برنامه: <http://127.0.0.1:8000> و Swagger: <http://127.0.0.1:8000/docs>

> 💡 اگر روی ویندوز با خطای build `lxml` مواجه شدید، از نسخه‌ی از پیش کامپایل‌شده استفاده کنید: `pip install --only-binary=:all: lxml` و سپس `pip install -r requirements.txt`.

## اپ دسکتاپ ویندوز

فایل `gui.py` سرور را در یک thread پس‌زمینه اجرا می‌کند و رابط کاربری را در یک پنجره بومی نشان می‌دهد (به WebView2 نیاز دارد که در ویندوز ۱۰ و ۱۱ معمولاً نصب است).

```powershell
pip install pywebview pyinstaller
python gui.py
```

**ساخت فایل `.exe`** (در PowerShell، همه در یک خط):

```powershell
pyinstaller --noconfirm --onefile --windowed --name EPUBAnalyzer --icon=icon.ico --collect-submodules uvicorn --collect-submodules pypdf --collect-submodules docx --hidden-import multipart gui.py
```

خروجی در `dist\EPUBAnalyzer.exe` ساخته می‌شود.

**ساخت فایل نصبی** با [Inno Setup](https://jrsoftware.org/isinfo.php): فایل `installer.iss` را باز کنید و *Build ← Compile* را بزنید (یا `ISCC installer.iss` را اجرا کنید). فایل نصبی در پوشه `installer_output\` ساخته می‌شود.

## API

| Endpoint | توضیح |
|---|---|
| `GET /` | رابط کاربری وب دوزبانه |
| `POST /api/analyze` | `multipart/form-data` با فیلد `file` (الزامی؛ EPUB/TXT/DOCX/PDF/FB2) و `words_per_minute` و `words_per_page` (اختیاری). خروجی شامل `book` (با `detected_language`)، `cover`، `statistics`، `chapters` (با `reading_time_minutes`) و `chapter_source` |
| `GET /health` | `{"status": "ok", "service": "EPUB Analyzer", "version": "1.1.1"}` |
| `GET /docs` | Swagger UI |

خطاها همیشه به شکل `{"success": false, "error": "..."}` هستند: `400` فایل انتخاب نشده یا خالی، `413` حجم بیش از حد، `415` پسوند غیرمجاز، `422` فایل نامعتبر/خراب/رمزگذاری‌شده/بدون متن، `500` خطای داخلی، `501` پکیج فرمت موردنیاز نصب نیست. Traceback هرگز نمایش داده نمی‌شود.

```bash
curl -F "file=@book.epub" http://127.0.0.1:8000/api/analyze
curl -F "file=@book.pdf"  http://127.0.0.1:8000/api/analyze
```

## الگوریتم شمارش

برای فایل‌های EPUB، هر سند Spine (به ترتیب خوانش) با BeautifulSoup به بلوک‌های متنی تبدیل می‌شود. `script`، `style`، `svg`، `img`، `nav` و بخش‌های `epub:type="toc|landmarks|page-list"` حذف می‌شوند. سپس متن با NFKC نرمال می‌شود، نویسه‌های نامرئی و کشیده حذف می‌شوند، فاصله‌ها فشرده می‌شوند و نیم‌فاصله (ZWNJ) حفظ می‌شود.

برای TXT/DOCX/PDF/FB2، متن به پاراگراف‌ها تقسیم شده و همان قواعد شمارش اعمال می‌شوند.

- **کلمه:** دنباله‌ای از حروف و ارقام یونیکد (و اعراب) که با نیم‌فاصله، آپوستروف یا خط‌تیره به هم می‌پیوندند (`کتاب‌خوانی`، `well-known`) یا عدد اعشاری/هزارگان (`3.14`). علائم نگارشی هرگز کلمه نیستند.
- **حروف:** نویسه‌های دسته `L*` یونیکد (بدون ارقام، فاصله و علائم).
- **حروف با فاصله:** حروف به‌علاوه فاصله‌های داخل متن.
- **کاراکترها:** با فاصله، بدون فاصله، و بدون فاصله و علائم نگارشی (`P*` و `S*`).
- **پاراگراف:** هر بلوک غیر‌عنوان که متن واقعی دارد. عنوان‌ها در کلمه، حرف و کاراکتر می‌آیند ولی پاراگراف و جمله حساب نمی‌شوند.
- **جمله:** پایان با `. ! ? ؟ ۔ …`. چند علامت پشت‌سرهم یک مرز است و مخفف‌هایی مثل `Dr.` و حروف اول نام مثل `J.` مرز نیستند.
- **فصل:**
  - اگر فهرست مطالب (TOC) موجود باشد، ورودی‌های TOC مبنا هستند. اگر یک فایل چند ورودی TOC با Anchor داشته باشد، فایل در همان نقاط به چند فصل تقسیم می‌شود.
  - در نبود TOC، اگر فایل بیش از یک تیتر H1 داشته باشد بر اساس H1 و در غیر این صورت بر اساس H2/H3 تقسیم می‌شود.
  - در نهایت اگر هیچ تیتری نباشد، هر بخش متنی معتبر یک فصل است.
  - جمع فصل‌ها همیشه با کل کتاب برابر است.
- **زبان:** بر اساس فراوانی نویسه‌های اسکریپت‌های لاتین، عربی (با تفکیک فارسی/عربی)، سیریلیک و CJK در ۲۰٬۰۰۰ نویسه‌ی اول.

## محدودیت‌ها

- صفحات EPUB ثابت نیستند، پس تعداد صفحات فقط یک تخمین است.
- متن PDF (به‌ویژه PDF‌های اسکن‌شده یا تصویری) ممکن است استخراج نشود و خطای `422` برگردد.
- برای TXT/DOCX/PDF، جلد و متادیتای غنی وجود ندارد؛ عنوان فایل به‌عنوان نام کتاب ثبت می‌شود.
- کتاب‌های دارای DRM یا رمزگذاری‌شده پشتیبانی نمی‌شوند.
- تشخیص جمله مبتنی بر قاعده است و برای مخفف‌های کمیاب ممکن است کمی خطا داشته باشد.
- تشخیص زبان heuristik است و برای متن‌های کوتاه ممکن است اشتباه کند.
- Starlette برای آپلودهای بزرگ‌تر از ۱ مگابایت ممکن است از یک فایل موقت استفاده کند که بلافاصله پس از درخواست حذف می‌شود.

## تنظیمات

ثابت‌های ابتدای `main.py` را تغییر دهید:

- `MAX_UPLOAD_SIZE` (پیش‌فرض ۱۰۰ مگابایت)
- `MAX_ZIP_ENTRIES`، `MAX_UNCOMPRESSED_SIZE`، `MAX_ENTRY_SIZE`، `MAX_COMPRESSION_RATIO`
- `MAX_PDF_PAGES` (پیش‌فرض ۳۰۰۰)
- `MAX_COVER_BYTES` (پیش‌فرض ۳ مگابایت)
- `DEFAULT_WORDS_PER_MINUTE` و `DEFAULT_WORDS_PER_PAGE`
- `SUPPORTED_FORMATS` (پیش‌فرض: `{.epub, .txt, .docx, .pdf, .fb2}`)

</div>

---

<a id="english"></a>

# English

## About

EPUB Analyzer is a lightweight tool that reads a book file entirely in memory and reports accurate text statistics: words, letters, characters, paragraphs, sentences, chapters, per-chapter breakdowns, book metadata, cover, detected language, reading time (overall and per chapter), and estimated page count. Supported formats: **EPUB, TXT, DOCX, PDF, FB2**. Persian, Arabic, English and other Latin-script languages are supported. The whole app (FastAPI backend plus HTML/CSS/JS frontend) lives in a single `main.py`, and it can also be packaged as a Windows desktop app.

## Features

- **Five book formats:** EPUB, TXT, DOCX, PDF, FB2
- **Bilingual UI (Persian/English)** with browser-language auto-detection and LocalStorage persistence
- Drag & drop or file picker upload, with file name, size, extension and processing status
- **Book cover display** for EPUB files (three detection fallbacks)
- **Automatic content language detection** (Persian, Arabic, English, Russian, Chinese) based on dominant script
- Structural EPUB validation (ZIP, `container.xml`, mimetype, DRM/encryption, ZIP bombs, path traversal)
- Files are processed in memory only and never stored on disk
- Navigation, table of contents, cover and duplicate pages are excluded from the counts
- Metadata: title, author, publisher, language, identifier, publication date, description
- Extra stats: average word, sentence and paragraph length, reading time (default 200 wpm) and estimated pages (default 300 words/page), both adjustable in the UI
- **Per-chapter reading time**
- **More accurate chapter splitting:** TOC anchor splits for multi-chapter files, heading-based fallback when TOC is absent
- Sortable, responsive chapter table
- Light and dark themes (saved in LocalStorage)
- Swagger UI at `/docs`

## Project structure

```text
epub-analyzer/
├── main.py            # Backend + Frontend (FastAPI)
├── gui.py             # Windows desktop wrapper (pywebview)
├── installer.iss      # Inno Setup script
├── icon.ico           # App icon
├── requirements.txt
├── README.md
└── docs/              # Logo and screenshots
```

## Quick start (web)

Requires Python 3.11 or newer.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open <http://127.0.0.1:8000> (Swagger: <http://127.0.0.1:8000/docs>).

> 💡 If `lxml` fails to build on Windows, install the pre-built wheel first: `pip install --only-binary=:all: lxml`, then `pip install -r requirements.txt`.

## Windows desktop app

`gui.py` starts the server in a background thread and shows the UI in a native window (needs the Microsoft WebView2 runtime, which ships with Windows 10/11).

```powershell
pip install pywebview pyinstaller
python gui.py
```

**Build the `.exe`** (single line in PowerShell):

```powershell
pyinstaller --noconfirm --onefile --windowed --name EPUBAnalyzer --icon=icon.ico --collect-submodules uvicorn --collect-submodules pypdf --collect-submodules docx --hidden-import multipart gui.py
```

The executable is created at `dist\EPUBAnalyzer.exe`.

**Build the installer** with [Inno Setup](https://jrsoftware.org/isinfo.php): open `installer.iss` and press *Build → Compile* (or run `ISCC installer.iss`). The setup file is written to `installer_output\`.

## API

| Endpoint | Description |
|---|---|
| `GET /` | Bilingual web UI |
| `POST /api/analyze` | `multipart/form-data`: `file` (required; EPUB/TXT/DOCX/PDF/FB2), `words_per_minute`, `words_per_page` (optional). Returns `book` (with `detected_language`), `cover`, `statistics`, `chapters` (with `reading_time_minutes`), `chapter_source` |
| `GET /health` | `{"status": "ok", "service": "EPUB Analyzer", "version": "1.1.1"}` |
| `GET /docs` | Swagger UI |

Errors always look like `{"success": false, "error": "..."}`: `400` no/empty file, `413` file too large, `415` wrong extension, `422` invalid/corrupt/encrypted/empty file, `500` internal error, `501` required format package not installed. Tracebacks are never exposed.

```bash
curl -F "file=@book.epub" http://127.0.0.1:8000/api/analyze
curl -F "file=@book.pdf"  http://127.0.0.1:8000/api/analyze
```

## How counting works

For EPUB files, each spine document (in reading order) is parsed with BeautifulSoup into text blocks. `script`, `style`, `svg`, `img`, `nav` and `epub:type="toc|landmarks|page-list"` parts are dropped. Text is normalised with NFKC, invisible characters and tatweel are removed, whitespace is collapsed, and the Persian half-space (ZWNJ) is kept.

For TXT/DOCX/PDF/FB2, text is split into paragraphs and the same counting rules apply.

- **Word:** a run of Unicode letters/digits (and diacritics), joined by ZWNJ, apostrophe or hyphen (`کتاب‌خوانی`, `well-known`), or a decimal/thousands number (`3.14`). Punctuation is never a word.
- **Letters:** characters in Unicode category `L*` (no digits, spaces or punctuation).
- **Letters with spaces:** letters plus the spaces inside the text.
- **Characters:** with spaces, without spaces, and without spaces and punctuation (`P*`, `S*`).
- **Paragraph:** any non-heading block with real text. Headings count towards words, letters and characters, but not paragraphs or sentences.
- **Sentence:** ends at `. ! ? ؟ ۔ …`. Repeated marks are one boundary; abbreviations such as `Dr.` and initials such as `J.` are not boundaries.
- **Chapter:**
  - When the TOC is present, TOC entries are the source of truth. If a file has multiple TOC entries with anchors, the file is split at those anchor points.
  - When TOC is absent, files with multiple H1s are split at H1; otherwise split at H2/H3.
  - If no headings exist, each valid text section is reported as a chapter.
  - Chapter totals always add up to the book total.
- **Language:** detected from character frequencies of Latin, Arabic (Persian vs Arabic disambiguated), Cyrillic and CJK scripts over the first 20,000 characters.

## Limitations

- EPUB pages are not fixed, so the page count is only an estimate.
- PDF text (especially scanned or image-only PDFs) may not be extractable, in which case a `422` error is returned.
- For TXT/DOCX/PDF, there is no cover and no rich metadata; the filename becomes the title.
- DRM-protected or encrypted books are not supported.
- Sentence detection is rule-based and may be slightly off for rare abbreviations.
- Language detection is heuristic and may misfire on short texts.
- Large uploads (over 1 MB) may be spooled to a temporary file by Starlette, which is deleted right after the request.

## Configuration

Edit the constants at the top of `main.py`:

- `MAX_UPLOAD_SIZE` (default 100 MB)
- `MAX_ZIP_ENTRIES`, `MAX_UNCOMPRESSED_SIZE`, `MAX_ENTRY_SIZE`, `MAX_COMPRESSION_RATIO`
- `MAX_PDF_PAGES` (default 3000)
- `MAX_COVER_BYTES` (default 3 MB)
- `DEFAULT_WORDS_PER_MINUTE`, `DEFAULT_WORDS_PER_PAGE`
- `SUPPORTED_FORMATS` (default: `{.epub, .txt, .docx, .pdf, .fb2}`)

---
