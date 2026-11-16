"""EPUB Analyzer: تحلیل آماری فایل‌های کتاب (EPUB, TXT, DOCX, PDF, FB2).

اجرا:  uvicorn main:app --reload
"""
from __future__ import annotations

# ============================== 1. Imports ==============================
import asyncio
import base64
import hashlib
import io
import logging
import math
import posixpath
import re
import unicodedata
import warnings
import zipfile
from urllib.parse import unquote

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString, Tag
from ebooklib import ITEM_DOCUMENT, epub
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

try:
    from docx import Document as DocxDocument
    _HAS_DOCX = True
except Exception:
    _HAS_DOCX = False

try:
    from pypdf import PdfReader
    _HAS_PDF = True
except Exception:
    _HAS_PDF = False

try:
    import lxml  # noqa: F401
    _XML_PARSER = "xml"
except Exception:
    _XML_PARSER = "html.parser"

# ============================ 2. Configuration ==========================
APP_NAME = "EPUB Analyzer"
APP_VERSION = "1.2.0"

MAX_UPLOAD_SIZE = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000
MAX_UNCOMPRESSED_SIZE = 400 * 1024 * 1024
MAX_ENTRY_SIZE = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
MAX_PDF_PAGES = 3000
MAX_COVER_BYTES = 3 * 1024 * 1024
DEFAULT_WORDS_PER_MINUTE = 200
DEFAULT_WORDS_PER_PAGE = 300

SUPPORTED_FORMATS = {".epub", ".txt", ".docx", ".pdf", ".fb2"}

logger = logging.getLogger("epub_analyzer")
warnings.filterwarnings("ignore", module="ebooklib")

# ======================== 3. FastAPI App Initialization =================
app = FastAPI(title=APP_NAME, version=APP_VERSION,
              description="Upload a book file (EPUB/TXT/DOCX/PDF/FB2) and get detailed text statistics.")


class AnalyzerError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def error_response(status: int, message: str) -> JSONResponse:
    return JSONResponse({"success": False, "error": message}, status_code=status)


# ============== 4-6. HTML Template, CSS Styles, JavaScript ==============
PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EPUB Analyzer</title>
<script>
(function () {
  var t = null, l = null;
  try { t = localStorage.getItem('theme'); l = localStorage.getItem('lang'); } catch (e) {}
  if (t !== 'dark' && t !== 'light') {
    t = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (l !== 'fa' && l !== 'en') {
    l = (navigator.language || '').toLowerCase().startsWith('fa') ? 'fa' : 'en';
  }
  document.documentElement.dataset.theme = t;
  document.documentElement.lang = l;
  document.documentElement.dir = l === 'fa' ? 'rtl' : 'ltr';
})();
</script>
<style>
:root {
  --bg: #eef2f1; --glass: rgba(255,255,255,.68); --solid: #ffffff; --ink: #15232b; --muted: #566870;
  --line: rgba(21,35,43,.13); --accent: #0f766e; --accent-soft: rgba(15,118,110,.12); --on-accent: #fff;
  --amber: rgba(201,140,40,.22); --teal: rgba(15,118,110,.20); --danger: #b42318; --danger-soft: rgba(180,35,24,.1);
  --shadow: 0 8px 30px rgba(21,35,43,.08);
  --font: "Vazirmatn", "Segoe UI", Tahoma, "Noto Naskh Arabic", system-ui, sans-serif;
  color-scheme: light;
}
:root[data-theme="dark"] {
  --bg: #0f1a1f; --glass: rgba(30,45,53,.62); --solid: #16242b; --ink: #e5eef0; --muted: #9db2b9;
  --line: rgba(229,238,240,.13); --accent: #45bfb1; --accent-soft: rgba(69,191,177,.14); --on-accent: #0b1a1d;
  --amber: rgba(224,163,70,.13); --teal: rgba(69,191,177,.13); --danger: #ff8f84; --danger-soft: rgba(255,143,132,.12);
  --shadow: 0 8px 30px rgba(0,0,0,.28);
  color-scheme: dark;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; min-height: 100vh; font-family: var(--font); color: var(--ink); line-height: 1.7;
  background: radial-gradient(60rem 30rem at 85% -10%, var(--teal), transparent 60%),
              radial-gradient(50rem 30rem at -5% 10%, var(--amber), transparent 60%), var(--bg);
  background-attachment: fixed;
}
.wrap { width: min(1080px, 100% - 2rem); margin-inline: auto; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.6rem 0 1rem; }
.brand { display: flex; align-items: center; gap: .9rem; }
.brand svg { width: 46px; height: 46px; flex: none; }
.brand h1 { margin: 0; font-size: 1.45rem; line-height: 1.2; letter-spacing: -.01em; }
.brand p { margin: .15rem 0 0; color: var(--muted); font-size: .92rem; }
.toolbar { display: flex; gap: .5rem; }
button { font: inherit; color: inherit; cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.icon-btn { width: 44px; height: 44px; border-radius: 14px; border: 1px solid var(--line); background: var(--glass);
  backdrop-filter: blur(10px); display: grid; place-items: center; }
.icon-btn svg { width: 20px; height: 20px; }
.lang-btn { width: 44px; height: 44px; border-radius: 14px; border: 1px solid var(--line); background: var(--glass);
  display: grid; place-items: center; font-weight: 700; font-size: .85rem; }
.card { background: var(--glass); border: 1px solid var(--line); border-radius: 20px; box-shadow: var(--shadow);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 1.4rem; }
h2 { margin: 0 0 1rem; font-size: 1.1rem; }
.drop { text-align: center; padding: 2.4rem 1.4rem; border: 2px dashed var(--line); transition: border-color .2s, background .2s; }
.drop.over { border-color: var(--accent); background: var(--accent-soft); }
.drop .book { width: 64px; height: 64px; color: var(--accent); }
.drop h2 { margin: .8rem 0 .3rem; font-size: 1.25rem; }
.hint { color: var(--muted); font-size: .9rem; margin: .2rem 0; }
.btn { border: 1px solid transparent; background: var(--accent); color: var(--on-accent); padding: .65rem 1.3rem;
  border-radius: 12px; font-weight: 600; }
.btn.ghost { background: transparent; color: var(--ink); border-color: var(--line); }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.actions { display: flex; flex-wrap: wrap; justify-content: center; gap: .6rem; margin-top: 1rem; }
.fileinfo { margin: 1.2rem auto 0; max-width: 560px; padding: .9rem 1rem; border-radius: 14px; background: var(--solid);
  border: 1px solid var(--line); text-align: start; }
.fileinfo .name { font-weight: 600; overflow-wrap: anywhere; direction: ltr; text-align: right; }
.chips { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .5rem; }
.chip { font-size: .82rem; padding: .1rem .7rem; border-radius: 99px; background: var(--accent-soft); }
.status { margin-top: .5rem; font-size: .88rem; color: var(--muted); display: flex; align-items: center; gap: .6rem; }
.spin { width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--line); border-top-color: var(--accent);
  animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { margin-top: 1rem; padding: .9rem 1.1rem; border-radius: 14px; background: var(--danger-soft);
  color: var(--danger); border: 1px solid var(--danger); display: flex; flex-wrap: wrap; gap: .8rem; align-items: center;
  justify-content: space-between; }
.error .btn { background: var(--danger); color: var(--solid); padding: .35rem 1rem; }
[hidden] { display: none !important; }
#results { display: grid; gap: 1.2rem; margin-top: 1.4rem; animation: rise .45s ease both; }
@keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.book-layout { display: flex; gap: 1.4rem; align-items: flex-start; flex-wrap: wrap; }
.book-layout .cover { max-width: 170px; max-height: 260px; border-radius: 12px; box-shadow: var(--shadow);
  flex: none; display: block; object-fit: contain; }
.book-layout dl.meta { flex: 1; min-width: 220px; }
dl.meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: .9rem 1.4rem; margin: 0; }
dl.meta dt { color: var(--muted); font-size: .82rem; }
dl.meta dd { margin: 0; font-weight: 500; overflow-wrap: anywhere; }
dl.meta > div.wide { grid-column: 1 / -1; }
dd.none { color: var(--muted); font-weight: 400; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem; }
.stat { display: flex; align-items: center; gap: .9rem; padding: 1.1rem; }
.stat .ico { width: 46px; height: 46px; border-radius: 14px; background: var(--accent-soft); color: var(--accent);
  display: grid; place-items: center; flex: none; }
.stat .ico svg { width: 24px; height: 24px; }
.stat .val { font-size: 1.55rem; font-weight: 700; line-height: 1.2; }
.stat .lbl { color: var(--muted); font-size: .88rem; }
.mini { padding: 1rem 1.1rem; background: var(--solid); border: 1px solid var(--line); border-radius: 14px; }
.mini .val { font-size: 1.25rem; font-weight: 700; }
.mini .lbl { color: var(--muted); font-size: .85rem; }
.mini label { display: flex; align-items: center; gap: .5rem; margin-top: .4rem; font-size: .82rem; color: var(--muted); }
.mini input { width: 5.5rem; padding: .25rem .5rem; border-radius: 8px; border: 1px solid var(--line);
  background: var(--bg); color: var(--ink); font: inherit; }
.note { margin: 1rem 0 0; color: var(--muted); font-size: .85rem; }
.tablewrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 14px; background: var(--solid); }
table { width: 100%; border-collapse: collapse; min-width: 640px; }
th, td { padding: .7rem .9rem; text-align: start; border-bottom: 1px solid var(--line); white-space: nowrap; }
td.title { white-space: normal; min-width: 14rem; }
tr:last-child td { border-bottom: 0; }
th { color: var(--muted); font-weight: 600; font-size: .85rem; background: var(--accent-soft); }
th button { background: none; border: 0; padding: 0; font-weight: 700; color: var(--ink); }
tbody tr:hover { background: var(--accent-soft); }
footer { text-align: center; color: var(--muted); font-size: .85rem; padding: 2rem 0 2.4rem; }
@media (max-width: 560px) { .brand p { display: none; } .drop { padding: 1.6rem 1rem; } }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <svg viewBox="0 0 48 48" aria-hidden="true"><rect x="2" y="2" width="44" height="44" rx="13" fill="var(--accent)"/>
        <path d="M14 14h13a5 5 0 0 1 5 5v15H19a5 5 0 0 1-5-5V14Z" fill="none" stroke="var(--on-accent)" stroke-width="2.4" stroke-linejoin="round"/>
        <path d="M19 21h8M19 26h8" stroke="var(--on-accent)" stroke-width="2.4" stroke-linecap="round"/></svg>
      <div><h1>EPUB Analyzer</h1><p data-i18n="tagline"></p></div>
    </div>
    <div class="toolbar">
      <button class="lang-btn" id="lang" type="button" aria-label="Language / زبان">EN</button>
      <button class="icon-btn" id="theme" type="button" data-i18n-aria="theme_toggle" data-i18n-title="theme_toggle" title="">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>
      </button>
    </div>
  </header>

  <main>
    <section class="card drop" id="drop" data-i18n-aria="drop_aria">
      <svg class="book" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z"/><path d="M4 21.5A2.5 2.5 0 0 1 6.5 19H20v2H6.5"/><path d="M9 8h7M9 12h5"/></svg>
      <h2 data-i18n="drop_title"></h2>
      <p class="hint" data-i18n="drop_hint"></p>
      <div class="actions"><button class="btn" id="pick" type="button" data-i18n="pick"></button></div>
      <p class="hint" id="format_hint"></p>
      <input type="file" id="input" accept=".epub,.txt,.docx,.pdf,.fb2,application/epub+zip,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf,application/x-fictionbook+xml" hidden>
      <div class="fileinfo" id="fileinfo" hidden>
        <div class="name" id="fname"></div>
        <div class="chips"><span class="chip" id="fsize"></span><span class="chip" id="fext"></span></div>
        <div class="status" id="status"></div>
        <div class="actions" style="justify-content:flex-start">
          <button class="btn ghost" id="again" type="button" data-i18n="again"></button>
          <button class="btn ghost" id="other" type="button" data-i18n="other"></button>
        </div>
      </div>
    </section>
    <div class="error" id="error" role="alert" hidden><span id="errmsg"></span><button class="btn" id="retry" type="button" data-i18n="retry"></button></div>

    <div id="results" hidden>
      <section class="card">
        <h2 data-i18n="book_info"></h2>
        <div class="book-layout">
          <img class="cover" id="cover" alt="cover" hidden>
          <dl class="meta" id="meta"></dl>
        </div>
      </section>
      <section><div class="grid" id="stats"></div></section>
      <section class="card"><h2 data-i18n="extra_stats"></h2><div class="grid" id="extra"></div>
        <p class="note" id="note"></p></section>
      <section class="card"><h2 data-i18n="chapter_stats"></h2>
        <div class="tablewrap"><table><thead><tr>
          <th scope="col">#</th><th scope="col" data-i18n="th_title"></th>
          <th scope="col" id="wordsTh" aria-sort="none"><button type="button" id="sortWords" data-i18n-title="sort_words"><span data-i18n="th_words"></span> <span id="arrow">⇅</span></button></th>
          <th scope="col" data-i18n="th_letters"></th>
          <th scope="col" data-i18n="th_paras"></th>
          <th scope="col" data-i18n="th_sents"></th>
          <th scope="col" data-i18n="th_rt"></th>
        </tr></thead><tbody id="rows"></tbody></table></div>
        <p class="note" id="chnote"></p></section>
    </div>
  </main>
  <footer>
    <a href="https://github.com/Hmidqorbani" target="_blank" rel="noopener noreferrer">Hmidqorbani</a>
    <span> — EPUB Analyzer، __VERSION__</span>
  </footer>
</div>

<script>
(() => {
  const MAX = __MAX_BYTES__;
  const ALLOWED = ['epub', 'txt', 'docx', 'pdf', 'fb2'];
  const $ = s => document.querySelector(s);
  const nf = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 });
  const nfEn = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
  const root = document.documentElement;
  let file = null, data = null, sortMode = 'none';
  let lang = root.lang === 'fa' ? 'fa' : 'en';

  const I18N = {
    fa: {
      tagline: 'کلمه‌ها، حرف‌ها، جمله‌ها و فصل‌های کتاب را بشمارید.',
      drop_title: 'فایل کتاب را اینجا رها کنید',
      drop_hint: 'یا از دکمه زیر برای انتخاب فایل استفاده کنید.',
      drop_aria: 'آپلود فایل کتاب',
      pick: 'انتخاب فایل', again: 'تحلیل مجدد', other: 'انتخاب فایل دیگر',
      retry: 'تلاش مجدد', theme_toggle: 'تغییر تم روشن/تیره',
      analyzing: 'در حال تحلیل کتاب…', done: 'تحلیل کامل شد.',
      book_info: 'اطلاعات کتاب', extra_stats: 'آمار تکمیلی', chapter_stats: 'آمار فصل‌ها',
      title: 'عنوان', author: 'نویسنده', publisher: 'ناشر', language: 'زبان کتاب',
      identifier: 'شناسه', pub_date: 'تاریخ انتشار', description: 'توضیحات',
      detected_lang: 'زبان تشخیص‌داده‌شده', not_recorded: 'ثبت نشده',
      words: 'کلمات', characters: 'کاراکترها (با فاصله)', chars_no_space: 'کاراکترها بدون فاصله',
      letters: 'حروف', letters_spaces: 'حروف با فاصله', paragraphs: 'پاراگراف‌ها',
      sentences: 'جمله‌ها', chapters: 'فصل‌ها',
      avg_word_len: 'میانگین طول کلمه (حرف)', avg_sent_len: 'میانگین طول جمله (کلمه)',
      avg_para_words: 'میانگین کلمات هر پاراگراف', chars_clean: 'کاراکتر بدون فاصله و علائم',
      reading_time: 'زمان مطالعه', est_pages: 'تعداد صفحات تخمینی',
      wpm_label: 'کلمه در دقیقه', wpp_label: 'کلمه در صفحه',
      note_extra: 'زمان مطالعه = کل کلمات ÷ سرعت مطالعه. صفحه‌های EPUB ثابت نیستند و تعداد صفحات فقط یک تخمین بر اساس تعداد کلمه است.',
      th_title: 'عنوان فصل', th_words: 'کلمات', th_letters: 'حروف', th_paras: 'پاراگراف‌ها', th_sents: 'جمله‌ها', th_rt: 'زمان مطالعه',
      sort_words: 'مرتب‌سازی بر اساس تعداد کلمات',
      ch_note_toc: 'فصل‌ها بر اساس فهرست مطالب (TOC) و ترتیب خوانش (Spine) تعیین شده‌اند؛ از جمله تقسیم فایل‌های چندفصلی بر اساس Anchorها.',
      ch_note_headings: 'این کتاب فهرست مطالب مشخصی ندارد؛ فصل‌ها بر اساس تیترهای (Heading) داخل فایل‌ها تقسیم شده‌اند.',
      ch_note_spine: 'این کتاب فصل‌بندی مشخصی ندارد؛ هر بخش متنی معتبر به‌عنوان یک فصل گزارش شده است.',
      ch_note_single: 'این فرمت معمولاً ساختار فصل ندارد و کل کتاب یک فصل در نظر گرفته می‌شود.',
      err_conn: 'ارتباط با سرور برقرار نشد.', err_ext: 'فرمت فایل پشتیبانی نمی‌شود.',
      err_empty: 'فایل انتخاب‌شده خالی است.', err_size: 'حجم فایل بیش از حد مجاز است.',
      err_generic: 'تحلیل فایل انجام نشد.',
      lang_fa: 'فارسی', lang_ar: 'عربی', lang_en: 'انگلیسی', lang_ru: 'روسی', lang_zh: 'چینی', lang_unknown: 'نامشخص',
      unit_byte: 'بایت', unit_kb: 'کیلوبایت', unit_mb: 'مگابایت',
      hour: 'ساعت', minute: 'دقیقه', less_min: 'کمتر از ۱ دقیقه', and: ' و ',
      format_hint_tpl: 'فرمت‌های پشتیبانی‌شده: EPUB، TXT، DOCX، PDF، FB2. حداکثر حجم: __MAX_MB__ مگابایت.'
    },
    en: {
      tagline: 'Count the words, letters, sentences and chapters of any book.',
      drop_title: 'Drop your book file here',
      drop_hint: 'Or use the button below to select a file.',
      drop_aria: 'Upload book file',
      pick: 'Choose file', again: 'Analyze again', other: 'Choose another file',
      retry: 'Retry', theme_toggle: 'Toggle light/dark theme',
      analyzing: 'Analyzing book…', done: 'Analysis complete.',
      book_info: 'Book information', extra_stats: 'Extra statistics', chapter_stats: 'Chapter statistics',
      title: 'Title', author: 'Author', publisher: 'Publisher', language: 'Language',
      identifier: 'Identifier', pub_date: 'Publication date', description: 'Description',
      detected_lang: 'Detected language', not_recorded: 'Not recorded',
      words: 'Words', characters: 'Characters (with spaces)', chars_no_space: 'Characters without spaces',
      letters: 'Letters', letters_spaces: 'Letters with spaces', paragraphs: 'Paragraphs',
      sentences: 'Sentences', chapters: 'Chapters',
      avg_word_len: 'Avg. word length (letters)', avg_sent_len: 'Avg. sentence length (words)',
      avg_para_words: 'Avg. words per paragraph', chars_clean: 'Chars without spaces & punctuation',
      reading_time: 'Reading time', est_pages: 'Estimated pages',
      wpm_label: 'words / minute', wpp_label: 'words / page',
      note_extra: 'Reading time = total words ÷ reading speed. EPUB pages are not fixed; page count is only an estimate based on word count.',
      th_title: 'Chapter title', th_words: 'Words', th_letters: 'Letters', th_paras: 'Paragraphs', th_sents: 'Sentences', th_rt: 'Reading time',
      sort_words: 'Sort by word count',
      ch_note_toc: 'Chapters are determined from the table of contents (TOC) and reading order (Spine), including splitting multi-chapter files by anchors.',
      ch_note_headings: 'This book has no clear table of contents; chapters were split by in-file headings.',
      ch_note_spine: 'This book has no chapter structure; each valid text section is reported as a chapter.',
      ch_note_single: 'This format usually has no chapter structure, so the whole book is treated as one chapter.',
      err_conn: 'Could not reach the server.', err_ext: 'File format not supported.',
      err_empty: 'Selected file is empty.', err_size: 'File size exceeds the limit.',
      err_generic: 'Analysis failed.',
      lang_fa: 'Persian', lang_ar: 'Arabic', lang_en: 'English', lang_ru: 'Russian', lang_zh: 'Chinese', lang_unknown: 'Unknown',
      unit_byte: 'B', unit_kb: 'KB', unit_mb: 'MB',
      hour: 'h', minute: 'min', less_min: 'Less than 1 min', and: ' ',
      format_hint_tpl: 'Supported formats: EPUB, TXT, DOCX, PDF, FB2. Max size: __MAX_MB__ MB.'
    }
  };
  const t = k => (I18N[lang] && I18N[lang][k]) || k;
  const num = n => (n === null || n === undefined) ? '—' : (lang === 'fa' ? nf : nfEn).format(n);

  const LANG_NAMES = {
    fa: () => t('lang_fa'), ar: () => t('lang_ar'), en: () => t('lang_en'),
    ru: () => t('lang_ru'), zh: () => t('lang_zh'), unknown: () => t('lang_unknown')
  };

  function applyStaticI18n() {
    root.lang = lang;
    root.dir = lang === 'fa' ? 'rtl' : 'ltr';
    for (const el of document.querySelectorAll('[data-i18n]')) {
      const key = el.dataset.i18n;
      if (I18N[lang][key] !== undefined) el.textContent = I18N[lang][key];
    }
    for (const el of document.querySelectorAll('[data-i18n-title]')) {
      const key = el.dataset.i18nTitle;
      if (I18N[lang][key] !== undefined) el.title = I18N[lang][key];
    }
    for (const el of document.querySelectorAll('[data-i18n-aria]')) {
      const key = el.dataset.i18nAria;
      if (I18N[lang][key] !== undefined) el.setAttribute('aria-label', I18N[lang][key]);
    }
    $('#lang').textContent = lang === 'fa' ? 'EN' : 'FA';
    $('#format_hint').textContent = t('format_hint_tpl').replace('__MAX_MB__', num(Math.round(MAX / 1048576)));
  }

  $('#lang').onclick = () => {
    lang = lang === 'fa' ? 'en' : 'fa';
    try { localStorage.setItem('lang', lang); } catch (e) {}
    applyStaticI18n();
    if (data) render();
  };

  $('#theme').onclick = () => {
    const th = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = th;
    try { localStorage.setItem('theme', th); } catch (e) {}
  };

  const bytesText = b => b < 1024 ? num(b) + ' ' + t('unit_byte')
    : b < 1048576 ? num(+(b / 1024).toFixed(2)) + ' ' + t('unit_kb')
    : num(+(b / 1048576).toFixed(2)) + ' ' + t('unit_mb');
  const showError = m => { $('#errmsg').textContent = m; $('#error').hidden = false; $('#retry').hidden = !file; };
  const hideError = () => { $('#error').hidden = true; };
  const setBusy = on => {
    $('#again').disabled = $('#other').disabled = $('#pick').disabled = on;
    $('#status').replaceChildren();
    if (on) {
      const s = document.createElement('span'); s.className = 'spin';
      $('#status').append(s, t('analyzing'));
    }
  };

  function setFile(f) {
    hideError();
    const ext = (f.name.includes('.') ? f.name.split('.').pop() : '').toLowerCase();
    if (!ALLOWED.includes(ext)) return showError(t('err_ext'));
    if (f.size === 0) return showError(t('err_empty'));
    if (f.size > MAX) return showError(t('err_size'));
    file = f;
    $('#fname').textContent = f.name;
    $('#fsize').textContent = bytesText(f.size);
    $('#fext').textContent = ext.toUpperCase();
    $('#fileinfo').hidden = false;
    analyze();
  }

  async function analyze() {
    if (!file) return;
    hideError(); setBusy(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('words_per_minute', $('#wpm') ? $('#wpm').value || 200 : 200);
    fd.append('words_per_page', $('#wpp') ? $('#wpp').value || 300 : 300);
    let msg = t('err_conn');
    try {
      const r = await fetch('/api/analyze', { method: 'POST', body: fd });
      let j = null;
      try { j = await r.json(); } catch (e) {}
      if (!r.ok || !j || !j.success) { msg = (j && j.error) || t('err_generic'); throw new Error(); }
      data = j; render();
      $('#status').textContent = t('done');
      $('#results').hidden = false;
      $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      $('#status').replaceChildren(); $('#results').hidden = true;
      showError(msg);
    } finally {
      $('#again').disabled = $('#other').disabled = $('#pick').disabled = false;
      if ($('#status').querySelector('.spin')) $('#status').replaceChildren();
    }
  }

  const ICONS = {
    words: '<path d="M4 7V5h16v2M12 5v14M9 19h6"/>',
    chars: '<path d="M5 19 12 5l7 14M8 14h8"/><path d="M4 21h16"/>',
    nospace: '<path d="M5 19 12 5l7 14M8 14h8"/>',
    letters: '<path d="M6 19V5l12 14V5"/>',
    lettersws: '<path d="M4 17V7h4a3 3 0 0 1 0 6H4M14 17v-4h6v4"/>',
    paragraphs: '<path d="M13 4v16M17 4v16M13 4H9a4 4 0 0 0 0 8h4"/>',
    sentences: '<path d="M4 7h16M4 12h10M4 17h13"/><circle cx="19" cy="17" r="1"/>',
    chapters: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z"/><path d="M9 8h7"/>'
  };
  const svg = p => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + p + '</svg>';

  function render() {
    const b = data.book, s = data.statistics;

    const cover = $('#cover');
    if (data.cover) { cover.src = data.cover; cover.hidden = false; }
    else { cover.hidden = true; cover.removeAttribute('src'); }

    const meta = $('#meta'); meta.replaceChildren();
    const detName = LANG_NAMES[b.detected_language] ? LANG_NAMES[b.detected_language]() : (b.detected_language || '—');
    const rows = [
      ['title', b.title], ['author', b.author], ['publisher', b.publisher],
      ['language', b.language], ['detected_lang', detName],
      ['identifier', b.identifier], ['pub_date', b.publication_date],
      ['description', b.description, true]
    ];
    rows.forEach(([k, v, wide]) => {
      const row = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = t(k); dd.textContent = v || t('not_recorded');
      if (!v) dd.className = 'none';
      if (wide) row.className = 'wide';
      row.append(dt, dd); meta.append(row);
    });

    const cards = [
      ['words', t('words'), s.words], ['chars', t('characters'), s.characters],
      ['nospace', t('chars_no_space'), s.characters_without_spaces],
      ['letters', t('letters'), s.letters], ['lettersws', t('letters_spaces'), s.letters_with_spaces],
      ['paragraphs', t('paragraphs'), s.paragraphs], ['sentences', t('sentences'), s.sentences],
      ['chapters', t('chapters'), s.chapters]];
    const grid = $('#stats'); grid.replaceChildren();
    cards.forEach(([ic, lbl, v]) => {
      const el = document.createElement('div'); el.className = 'card stat';
      el.innerHTML = '<div class="ico">' + svg(ICONS[ic]) + '</div><div><div class="val"></div><div class="lbl"></div></div>';
      el.querySelector('.val').textContent = num(v); el.querySelector('.lbl').textContent = lbl;
      grid.append(el);
    });

    renderExtra(); renderRows();
    const src = data.chapter_source;
    $('#chnote').textContent = src === 'toc' ? t('ch_note_toc')
      : src === 'headings' ? t('ch_note_headings')
      : src === 'single' ? t('ch_note_single')
      : t('ch_note_spine');
  }

  function mini(lbl, value, input) {
    const el = document.createElement('div'); el.className = 'mini';
    el.innerHTML = '<div class="val"></div><div class="lbl"></div>';
    el.querySelector('.val').textContent = value; el.querySelector('.lbl').textContent = lbl;
    if (input) el.append(input);
    return el;
  }
  function field(id, text, value, max) {
    const l = document.createElement('label'); l.textContent = text;
    const i = document.createElement('input'); i.type = 'number'; i.id = id; i.min = 1; i.max = max; i.value = value;
    i.oninput = updateEstimates; l.append(i); return l;
  }
  function renderExtra() {
    const s = data.statistics, ex = $('#extra');
    const wpm = $('#wpm') ? $('#wpm').value : s.words_per_minute, wpp = $('#wpp') ? $('#wpp').value : s.words_per_page;
    ex.replaceChildren(
      mini(t('avg_word_len'), num(s.average_word_length)),
      mini(t('avg_sent_len'), num(s.average_sentence_length)),
      mini(t('avg_para_words'), num(s.average_paragraph_words)),
      mini(t('chars_clean'), num(s.characters_without_spaces_and_punctuation)),
      mini(t('reading_time'), '', field('wpm', t('wpm_label'), wpm, 5000)),
      mini(t('est_pages'), '', field('wpp', t('wpp_label'), wpp, 10000)));
    ex.children[4].id = 'rt'; ex.children[5].id = 'pg';
    updateEstimates();
  }
  function updateEstimates() {
    const w = data.statistics.words;
    const wpm = Math.max(1, +$('#wpm').value || 200), wpp = Math.max(1, +$('#wpp').value || 300);
    const total = Math.round(w / wpm), h = Math.floor(total / 60), m = total % 60;
    let rt;
    if (total === 0) rt = t('less_min');
    else if (lang === 'fa') rt = (h ? num(h) + ' ' + t('hour') : '') + (h && m ? t('and') : '') + (m ? num(m) + ' ' + t('minute') : '');
    else rt = (h ? h + t('hour') : '') + (h && m ? ' ' + t('and') + ' ' : '') + (m ? m + ' ' + t('minute') : '');
    $('#rt .val').textContent = rt;
    $('#pg .val').textContent = num(Math.ceil(w / wpp));
    $('#note').textContent = t('note_extra');
  }

  function renderRows() {
    let list = data.chapters.slice();
    if (sortMode === 'desc') list.sort((a, b) => b.words - a.words);
    if (sortMode === 'asc') list.sort((a, b) => a.words - b.words);
    $('#arrow').textContent = sortMode === 'desc' ? '↓' : sortMode === 'asc' ? '↑' : '⇅';
    $('#wordsTh').setAttribute('aria-sort', sortMode === 'desc' ? 'descending' : sortMode === 'asc' ? 'ascending' : 'none');
    const tb = $('#rows'); tb.replaceChildren();
    list.forEach(c => {
      const tr = document.createElement('tr');
      const rt = c.reading_time_minutes;
      const rtText = rt > 0 ? (rt < 1 ? '<1' : num(rt)) + ' ' + t('minute') : '—';
      [num(c.index), c.title, num(c.words), num(c.letters), num(c.paragraphs), num(c.sentences), rtText].forEach((txt, i) => {
        const td = document.createElement('td'); td.textContent = txt; if (i === 1) td.className = 'title'; tr.append(td);
      });
      tb.append(tr);
    });
  }
  $('#sortWords').onclick = () => {
    sortMode = sortMode === 'none' ? 'desc' : sortMode === 'desc' ? 'asc' : 'none';
    renderRows();
  };

  const input = $('#input'), drop = $('#drop');
  $('#pick').onclick = $('#other').onclick = () => input.click();
  $('#again').onclick = $('#retry').onclick = analyze;
  input.onchange = () => { if (input.files[0]) setFile(input.files[0]); input.value = ''; };
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
  ['dragover', 'drop'].forEach(ev => window.addEventListener(ev, e => e.preventDefault()));

  applyStaticI18n();
})();
</script>
</body>
</html>
"""

PAGE_HTML = (PAGE_TEMPLATE
             .replace("__MAX_MB__", f"{MAX_UPLOAD_SIZE // (1024 * 1024):,}")
             .replace("__MAX_BYTES__", str(MAX_UPLOAD_SIZE))
             .replace("__VERSION__", APP_VERSION))


# ========================== 7. Utility Functions ========================
def nonneg_int(value: int, default: int, upper: int) -> int:
    return default if value is None or value < 1 else min(value, upper)


def clean_str(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _filename_to_title(filename: str | None) -> str:
    base = posixpath.basename(filename or "").rsplit(".", 1)[0]
    return clean_str(base.replace("_", " ").replace("-", " ")) or "کتاب"


# ========================== 8. EPUB Validation ==========================
_FONT_OBFUSCATION = ("http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC")


def validate_epub(data: bytes) -> None:
    buf = io.BytesIO(data)
    if not zipfile.is_zipfile(buf):
        raise AnalyzerError(422, "این فایل یک EPUB معتبر نیست (ساختار ZIP تشخیص داده نشد).")
    try:
        with zipfile.ZipFile(buf) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise AnalyzerError(422, "تعداد فایل‌های داخل EPUB غیرعادی است.")
            total = 0
            for info in infos:
                parts = info.filename.replace("\\", "/").split("/")
                if info.filename.startswith(("/", "\\")) or ".." in parts:
                    raise AnalyzerError(422, "مسیرهای نامعتبر داخل فایل وجود دارد.")
                if info.flag_bits & 0x1:
                    raise AnalyzerError(422, "فایل رمزگذاری‌شده است.")
                if info.file_size > MAX_ENTRY_SIZE:
                    raise AnalyzerError(422, "حجم یکی از فایل‌های داخلی بیش از حد مجاز است.")
                if info.file_size > (1 << 20) and info.compress_size and \
                        info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                    raise AnalyzerError(422, "فایل مشکوک به ZIP Bomb است.")
                total += info.file_size
            if total > MAX_UNCOMPRESSED_SIZE:
                raise AnalyzerError(422, "حجم محتوای EPUB پس از باز شدن بیش از حد مجاز است.")
            names = {i.filename for i in infos}
            if "META-INF/container.xml" not in names:
                raise AnalyzerError(422, "ساختار EPUB نامعتبر است (container.xml یافت نشد).")
            if "mimetype" in names and zf.open("mimetype").read(64).strip() != b"application/epub+zip":
                raise AnalyzerError(422, "نوع MIME با EPUB مطابقت ندارد.")
            if "META-INF/encryption.xml" in names:
                algos = re.findall(r'Algorithm="([^"]+)"', zf.read("META-INF/encryption.xml").decode("utf-8", "ignore"))
                if any(a not in _FONT_OBFUSCATION for a in algos):
                    raise AnalyzerError(422, "این کتاب با DRM محافظت شده است.")
    except AnalyzerError:
        raise
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, OSError, ValueError):
        raise AnalyzerError(422, "فایل EPUB خراب است یا قابل خواندن نیست.")


# ========================= 9. Text Utilities ============================
_STRIP = dict.fromkeys(map(ord, "\u00ad\u200b\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                                "\u2066\u2067\u2068\u2069\ufeff\u0640"))


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_STRIP)
    return re.sub(r"\s+", " ", text).strip()


_MARKS = "\u0300-\u036f\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed"
_W = rf"(?:[^\W_]|[{_MARKS}])"
WORD_RE = re.compile(rf"\d+(?:[.,٫٬]\d+)+(?![^\W_])|{_W}+(?:[\u200c'’\-\u2010]{_W}+)*")


def count_words(text: str) -> int:
    return sum(1 for _ in WORD_RE.finditer(text))


def count_characters(text: str) -> dict[str, int]:
    letters = sum(map(str.isalpha, text))
    spaces = text.count(" ")
    punct = sum(1 for ch in text if not ch.isalnum() and unicodedata.category(ch)[0] in "PS")
    return {"letters": letters, "spaces": spaces, "characters": len(text),
            "characters_without_spaces": len(text) - spaces,
            "characters_clean": len(text) - spaces - punct}


_SENT_END = re.compile(r"([.!?؟۔…]+)[\"'”’»)\]]*(?=\s|$)")
_ABBREV = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs"}
_LAST_WORD = re.compile(r"([^\W\d_]+)$")


def count_sentences(text: str) -> int:
    count, start = 0, 0
    for m in _SENT_END.finditer(text):
        seg = text[start:m.start()]
        if not WORD_RE.search(seg):
            start = m.end()
            continue
        if m.group(1) == ".":
            last = _LAST_WORD.search(seg)
            if last and ((len(last[1]) == 1 and last[1].isupper()) or last[1].lower() in _ABBREV):
                continue
        count += 1
        start = m.end()
    return count + (1 if WORD_RE.search(text[start:]) else 0)


# ========================= 10. Language Detection ======================
_PERSIAN_SPECIFIC = set("پچژگکیۀ")
_ARABIC_RANGE = [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]


def _in_ranges(ch: str, ranges) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in ranges)


def detect_language(text: str) -> str:
    counts = {"fa": 0, "ar": 0, "en": 0, "ru": 0, "zh": 0}
    sample = text[:20000]
    for ch in sample:
        if _in_ranges(ch, _ARABIC_RANGE):
            if ch in _PERSIAN_SPECIFIC:
                counts["fa"] += 1
            else:
                counts["ar"] += 1
        elif "a" <= ch.lower() <= "z":
            counts["en"] += 1
        elif 0x0400 <= ord(ch) <= 0x04FF:
            counts["ru"] += 1
        elif 0x4E00 <= ord(ch) <= 0x9FFF:
            counts["zh"] += 1
    total_arabic = counts["fa"] + counts["ar"]
    if total_arabic > 0 and counts["fa"] / total_arabic > 0.01:
        counts["fa"] += counts["ar"]
        counts["ar"] = 0
    if not any(counts.values()):
        return "unknown"
    return max(counts, key=counts.get)


# ======================== 11. Block Extraction =========================
BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "blockquote", "section", "article", "aside", "tr", "td", "th", "table",
              "dd", "dt", "dl", "figcaption", "figure", "pre", "header", "footer", "main", "body", "caption", "hr",
              "h1", "h2", "h3", "h4", "h5", "h6"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
SKIP_TAGS = {"script", "style", "svg", "math", "img", "head", "nav", "audio", "video", "canvas", "object", "iframe"}
NAV_TYPES = {"toc", "landmarks", "page-list"}
NON_CHAPTER_TYPES = {"toc", "landmarks", "cover", "titlepage", "halftitlepage", "copyright-page"}


def _types(tag: Tag) -> set[str]:
    raw = f"{tag.get('epub:type') or ''} {tag.get('role') or ''}"
    return {t.removeprefix("doc-") for t in raw.split()}


def _emit_text(buf, out, in_heading):
    if buf:
        text = normalize_text("".join(buf))
        buf.clear()
        if WORD_RE.search(text):
            out.append((text, in_heading))


def extract_blocks(soup: BeautifulSoup) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    buf: list[str] = []

    def walk(node, in_heading):
        for child in node.children:
            if isinstance(child, NavigableString):
                if not isinstance(child, PreformattedString):
                    buf.append(str(child))
            elif isinstance(child, Tag):
                name = (child.name or "").lower()
                if name in SKIP_TAGS or _types(child) & NAV_TYPES:
                    continue
                if name == "br":
                    buf.append(" ")
                elif name in BLOCK_TAGS:
                    inner = in_heading or name in HEADING_TAGS
                    _emit_text(buf, out, in_heading)
                    walk(child, inner)
                    _emit_text(buf, out, inner)
                else:
                    walk(child, in_heading)

    walk(soup, False)
    _emit_text(buf, out, False)
    return out


def extract_blocks_marked(soup: BeautifulSoup, fragment_titles: dict[str, str] | None = None,
                          split_level: int | None = None) -> list[tuple[str, bool, str | None]]:
    out: list[tuple[str, bool, str | None]] = []
    buf: list[str] = []
    pending = [None]

    def flush(in_heading):
        if buf:
            text = normalize_text("".join(buf))
            buf.clear()
            if WORD_RE.search(text):
                marker = pending[0]
                pending[0] = None
                out.append((text, in_heading, marker))

    def walk(node, in_heading):
        for child in node.children:
            if isinstance(child, NavigableString):
                if not isinstance(child, PreformattedString):
                    buf.append(str(child))
            elif isinstance(child, Tag):
                name = (child.name or "").lower()
                if name in SKIP_TAGS or _types(child) & NAV_TYPES:
                    continue
                marker = None
                cid = child.get("id")
                if fragment_titles and cid and cid in fragment_titles:
                    marker = fragment_titles[cid]
                elif split_level is not None and name in HEADING_TAGS:
                    if HEADING_LEVELS.get(name, 99) <= split_level:
                        txt = normalize_text(child.get_text())
                        marker = (txt[:120] or None) if txt else None
                if marker is not None and not in_heading:
                    flush(in_heading)
                    pending[0] = marker
                if name == "br":
                    buf.append(" ")
                elif name in BLOCK_TAGS:
                    inner = in_heading or name in HEADING_TAGS
                    flush(in_heading)
                    walk(child, inner)
                    flush(inner)
                else:
                    walk(child, in_heading)

    walk(soup, False)
    flush(False)
    return out


def group_by_markers(marked: list[tuple[str, bool, str | None]]) -> list[dict]:
    groups: list[dict] = []
    current: dict = {"title": None, "blocks": []}
    for text, heading, marker in marked:
        if marker is not None and (current["blocks"] or current["title"]):
            groups.append(current)
            current = {"title": marker, "blocks": []}
        elif marker is not None:
            current["title"] = marker
        current["blocks"].append((text, heading))
    if current["blocks"] or current["title"]:
        groups.append(current)
    while len(groups) > 1 and groups[0]["blocks"] and all(h for _, h in groups[0]["blocks"]):
        groups[1]["blocks"] = groups[0]["blocks"] + groups[1]["blocks"]
        groups = groups[1:]
    return groups


def is_non_chapter_doc(soup: BeautifulSoup, blocks: list[tuple[str, bool]]) -> bool:
    body = soup.body or soup
    kinds = _types(body) if isinstance(body, Tag) else set()
    children = [c for c in body.children if isinstance(c, Tag)]
    if len(children) == 1:
        kinds |= _types(children[0])
    if kinds & NON_CHAPTER_TYPES:
        return True
    links = soup.find_all("a")
    total = sum(len(t) for t, _ in blocks)
    link_chars = sum(len(normalize_text(a.get_text())) for a in links)
    return len(links) >= 5 and total > 0 and link_chars / total > 0.7


# ========================== 12. Text Metrics ===========================
STAT_KEYS = ("words", "letters", "spaces", "characters", "characters_without_spaces", "characters_clean",
             "paragraphs", "sentences", "paragraph_words")


def analyze_blocks(blocks: list[tuple[str, bool]]) -> dict[str, int]:
    stats = dict.fromkeys(STAT_KEYS, 0)
    for text, heading in blocks:
        words = count_words(text)
        chars = count_characters(text)
        stats["words"] += words
        for key in ("letters", "spaces", "characters", "characters_without_spaces", "characters_clean"):
            stats[key] += chars[key]
        if not heading:
            stats["paragraphs"] += 1
            stats["sentences"] += count_sentences(text)
            stats["paragraph_words"] += words
    return stats


# =========================== 13. Chapter Analysis =======================
def _norm_href(href: str | None) -> str:
    if not href:
        return ""
    path = unquote(href.split("#")[0])
    return posixpath.normpath(path) if path else ""


def _parse_href(href: str | None) -> tuple[str, str]:
    if not href:
        return "", ""
    path, _, frag = href.partition("#")
    return _norm_href(path), unquote(frag)


def toc_leaves(items) -> list[tuple[str, str]]:
    result = []
    for it in items:
        if isinstance(it, (tuple, list)) and len(it) == 2 and isinstance(it[1], (list, tuple)):
            sub = toc_leaves(it[1])
            if sub:
                result += sub
            elif getattr(it[0], "href", None):
                result.append((clean_str(getattr(it[0], "title", "")) or "", it[0].href))
        elif getattr(it, "href", None):
            result.append((clean_str(getattr(it, "title", "")) or "", it.href))
    return result


def _find_doc(docs: list[dict], path: str) -> dict | None:
    if not path:
        return None
    by_path = {d["name"]: d for d in docs}
    doc = by_path.get(path)
    if doc is not None:
        return doc
    for p, d in by_path.items():
        if p.endswith("/" + path):
            return d
    base = posixpath.basename(path)
    matches = [d for d in docs if posixpath.basename(d["name"]) == base]
    return matches[0] if len(matches) == 1 else None


def _get_doc_sections(doc: dict, toc_entries: list[tuple[str, str | None]]) -> list[dict]:
    with_frag = [(ttl, frag) for ttl, frag in toc_entries if frag]
    without_frag = [ttl for ttl, frag in toc_entries if not frag]

    if len(with_frag) >= 1:
        frag_titles = {frag: ttl for ttl, frag in with_frag}
        marked = extract_blocks_marked(doc["soup"], fragment_titles=frag_titles)
        sections = group_by_markers(marked)
        if sections and sections[0]["title"] is None and without_frag:
            sections[0]["title"] = without_frag[0]
        return sections

    if without_frag:
        return [{"title": without_frag[0], "blocks": extract_blocks(doc["soup"])}]

    for level in (1, 2, 3):
        marked = extract_blocks_marked(doc["soup"], split_level=level)
        sections = group_by_markers(marked)
        if len(sections) > 1:
            return sections
        if len(sections) == 1 and sections[0]["title"]:
            return sections
    return [{"title": None, "blocks": extract_blocks(doc["soup"])}]


def analyze_chapters(book: epub.EpubBook) -> tuple[list[dict], str]:
    docs: list[dict] = []
    seen = set()
    for entry in book.spine:
        idref = entry[0] if isinstance(entry, (tuple, list)) else entry
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ITEM_DOCUMENT or isinstance(item, epub.EpubNav):
            continue
        raw = item.content
        if not raw:
            continue
        soup = BeautifulSoup(raw, "html.parser")
        blocks = extract_blocks(soup)
        if not blocks or is_non_chapter_doc(soup, blocks):
            continue
        digest = hashlib.sha1("\n".join(t for t, _ in blocks).encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        docs.append({"name": _norm_href(item.get_name()), "soup": soup, "blocks": blocks})

    if not docs:
        raise AnalyzerError(422, "در این فایل محتوای متنی قابل‌خواندن پیدا نشد.")

    toc_map: dict[int, list[tuple[str, str | None]]] = {}
    for title, href in toc_leaves(book.toc or []):
        path, frag = _parse_href(href)
        doc = _find_doc(docs, path)
        if doc is not None:
            toc_map.setdefault(id(doc), []).append((title, frag or None))

    chapters: list[dict] = []
    for doc in docs:
        toc_entries = toc_map.get(id(doc), [])
        sections = _get_doc_sections(doc, toc_entries)
        for sec in sections:
            if not sec["blocks"]:
                continue
            if sec["title"] is None:
                if chapters:
                    chapters[-1]["blocks"].extend(sec["blocks"])
                else:
                    chapters.append({"title": None, "blocks": sec["blocks"]})
            else:
                chapters.append({"title": sec["title"], "blocks": sec["blocks"]})

    if not chapters:
        raise AnalyzerError(422, "فصلی در این کتاب پیدا نشد.")
    for i, ch in enumerate(chapters, 1):
        if not ch["title"]:
            ch["title"] = f"بخش {i}"

    if toc_map:
        source = "toc"
    elif any(len(_get_doc_sections(d, [])) > 1 for d in docs):
        source = "headings"
    else:
        source = "spine"
    return chapters, source


# ========================= 14. Metadata & Cover ========================
def extract_metadata(book: epub.EpubBook) -> dict:
    def values(name: str) -> list[str]:
        try:
            found = [clean_str(v) for v, _ in book.get_metadata("DC", name)]
        except Exception:
            return []
        return [v for v in found if v]

    description = values("description")
    if description:
        description = clean_str(BeautifulSoup(description[0], "html.parser").get_text(" "))
    authors = values("creator")
    first = lambda name: (values(name) or [None])[0]  # noqa: E731
    return {"title": first("title"), "author": ", ".join(authors) if authors else None,
            "publisher": first("publisher"), "language": first("language"), "identifier": first("identifier"),
            "publication_date": first("date"), "description": description or None}


def extract_cover(book: epub.EpubBook) -> str | None:
    """تشخیص جلد با سه روش fallback: OPF meta، properties، و نام فایل."""

    def _to_data_url(item) -> str | None:
        try:
            content = getattr(item, "content", None)
            if content is None and hasattr(item, "get_content"):
                try:
                    content = item.get_content()
                except Exception:
                    content = None
            if not content or not isinstance(content, (bytes, bytearray)):
                return None
            if len(content) > MAX_COVER_BYTES:
                return None
            mime = None
            for attr in ("media_type", "content_type", "mediaType"):
                mime = getattr(item, attr, None)
                if mime:
                    break
            if not mime:
                name = (getattr(item, "file_name", "") or "").lower()
                if name.endswith(".png"): mime = "image/png"
                elif name.endswith(".gif"): mime = "image/gif"
                elif name.endswith(".webp"): mime = "image/webp"
                elif name.endswith(".svg"): mime = "image/svg+xml"
                else: mime = "image/jpeg"
            if not isinstance(mime, str) or not mime.startswith("image/"):
                return None
            return f"data:{mime};base64,{base64.b64encode(bytes(content)).decode('ascii')}"
        except Exception:
            return None

    # روش ۱: OPF meta name="cover" content="<id>"
    try:
        meta = book.get_metadata("OPF", "cover")
        for entry in meta or []:
            cover_id = None
            if isinstance(entry, tuple) and len(entry) == 2:
                val, attrs = entry
                if isinstance(attrs, dict):
                    cover_id = attrs.get("content") or attrs.get("name")
                if not cover_id and isinstance(val, str):
                    cover_id = val
            elif isinstance(entry, str):
                cover_id = entry
            if cover_id:
                item = book.get_item_with_id(cover_id)
                if item is not None:
                    url = _to_data_url(item)
                    if url:
                        return url
    except Exception:
        pass

    # روش ۲: item با properties شامل "cover-image"
    try:
        for item in book.get_items():
            props = getattr(item, "properties", None) or []
            if isinstance(props, (list, tuple)) and "cover-image" in props:
                url = _to_data_url(item)
                if url:
                    return url
    except Exception:
        pass

    # روش ۳: تصویری که در نام فایلش "cover" هست
    try:
        for item in book.get_items():
            try:
                item_type = item.get_type() if hasattr(item, "get_type") else None
            except Exception:
                item_type = None
            if item_type != 1:  # ITEM_IMAGE
                continue
            name = (getattr(item, "file_name", "") or "").lower()
            if "cover" in name:
                url = _to_data_url(item)
                if url:
                    return url
    except Exception:
        pass

    return None


# ======================== 15. Format Analyzers =========================
def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "windows-1256", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _txt_to_blocks(text: str) -> list[tuple[str, bool]]:
    blocks = []
    for para in re.split(r"\n\s*\n", text):
        norm = normalize_text(para)
        if WORD_RE.search(norm):
            blocks.append((norm, False))
    if not blocks:
        norm = normalize_text(text)
        if WORD_RE.search(norm):
            blocks.append((norm, False))
    return blocks


def analyze_txt(data: bytes, filename: str, wpm: int, wpp: int) -> dict:
    blocks = _txt_to_blocks(_decode_text(data))
    if not blocks:
        raise AnalyzerError(422, "متنی در فایل TXT پیدا نشد.")
    title = _filename_to_title(filename)
    return _build_response(
        meta={"title": title, "author": None, "publisher": None, "language": None,
              "identifier": None, "publication_date": None, "description": None},
        chapters_data=[{"title": title, "blocks": blocks}],
        source="single", cover=None, wpm=wpm, wpp=wpp)


def analyze_docx(data: bytes, filename: str, wpm: int, wpp: int) -> dict:
    if not _HAS_DOCX:
        raise AnalyzerError(501, "پشتیبانی DOCX روی سرور نصب نیست (python-docx).")
    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception:
        raise AnalyzerError(422, "فایل DOCX نامعتبر است.")

    chapters: list[dict] = []
    current = {"title": None, "blocks": []}
    for para in doc.paragraphs:
        text = normalize_text(para.text or "")
        if not text or not WORD_RE.search(text):
            continue
        style = ""
        try:
            style = (para.style.name or "").lower() if para.style else ""
        except Exception:
            style = ""
        is_heading = style.startswith("heading") or style == "title"
        if is_heading:
            if current["blocks"]:
                chapters.append(current)
                current = {"title": text, "blocks": [(text, True)]}
            else:
                current["title"] = current["title"] or text
                current["blocks"].append((text, True))
        else:
            current["blocks"].append((text, False))
    if current["blocks"]:
        chapters.append(current)
    if not chapters:
        raise AnalyzerError(422, "متنی در DOCX پیدا نشد.")

    title = _filename_to_title(filename)
    if len(chapters) == 1 and not chapters[0]["title"]:
        chapters[0]["title"] = title
    return _build_response(
        meta={"title": title, "author": None, "publisher": None, "language": None,
              "identifier": None, "publication_date": None, "description": None},
        chapters_data=chapters,
        source="headings" if len(chapters) > 1 else "single",
        cover=None, wpm=wpm, wpp=wpp)


def analyze_pdf(data: bytes, filename: str, wpm: int, wpp: int) -> dict:
    if not _HAS_PDF:
        raise AnalyzerError(501, "پشتیبانی PDF روی سرور نصب نیست (pypdf).")
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        raise AnalyzerError(422, "فایل PDF نامعتبر است.")
    try:
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise AnalyzerError(422, "PDF رمزگذاری‌شده قابل پردازش نیست.")
            except AnalyzerError:
                raise
            except Exception:
                raise AnalyzerError(422, "PDF رمزگذاری‌شده قابل پردازش نیست.")
    except AnalyzerError:
        raise
    except Exception:
        pass

    if len(reader.pages) > MAX_PDF_PAGES:
        raise AnalyzerError(422, f"تعداد صفحات PDF بیش از {MAX_PDF_PAGES} است.")

    blocks: list[tuple[str, bool]] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        for para in re.split(r"\n\s*\n", text):
            norm = normalize_text(para)
            if WORD_RE.search(norm):
                blocks.append((norm, False))

    if not blocks:
        raise AnalyzerError(422, "متنی در PDF پیدا نشد (شاید اسکن‌شده یا تصویری باشد).")

    title = _filename_to_title(filename)
    return _build_response(
        meta={"title": title, "author": None, "publisher": None, "language": None,
              "identifier": None, "publication_date": None, "description": None},
        chapters_data=[{"title": title, "blocks": blocks}],
        source="single", cover=None, wpm=wpm, wpp=wpp)


def analyze_fb2(data: bytes, filename: str, wpm: int, wpp: int) -> dict:
    head = data[:200].decode("ascii", errors="ignore")
    m = re.search(r'encoding=["\']([^"\']+)', head)
    enc = m.group(1) if m else "utf-8"
    try:
        text = data.decode(enc)
    except (LookupError, UnicodeDecodeError):
        text = data.decode("utf-8", errors="replace")
    try:
        soup = BeautifulSoup(text, _XML_PARSER)
    except Exception:
        raise AnalyzerError(422, "فایل FB2 نامعتبر است.")

    meta = {"title": None, "author": None, "publisher": None, "language": None,
            "identifier": None, "publication_date": None, "description": None}
    ti = soup.find("title-info")
    if ti:
        bt = ti.find("book-title")
        if bt:
            meta["title"] = clean_str(bt.get_text())
        authors = []
        for a in ti.find_all("author"):
            fn = a.find("first-name")
            ln = a.find("last-name")
            full = " ".join(x for x in [(fn.get_text() if fn else ""), (ln.get_text() if ln else "")] if x).strip()
            if full:
                authors.append(full)
        if authors:
            meta["author"] = ", ".join(authors)
        lang = ti.find("lang")
        if lang:
            meta["language"] = clean_str(lang.get_text())
        ann = ti.find("annotation")
        if ann:
            meta["description"] = clean_str(ann.get_text(" "))
    if not meta["title"]:
        meta["title"] = _filename_to_title(filename)

    body = soup.find("body")
    if body is None:
        raise AnalyzerError(422, "بدنه FB2 پیدا نشد.")

    chapters: list[dict] = []
    for section in body.find_all("section", recursive=False):
        title_el = section.find("title", recursive=False)
        title = clean_str(title_el.get_text(" ")) if title_el else None
        blocks: list[tuple[str, bool]] = []
        for p in section.find_all("p"):
            norm = normalize_text(p.get_text(" "))
            if WORD_RE.search(norm):
                blocks.append((norm, False))
        if blocks:
            chapters.append({"title": title, "blocks": blocks})

    if not chapters:
        blocks: list[tuple[str, bool]] = []
        for p in body.find_all("p"):
            norm = normalize_text(p.get_text(" "))
            if WORD_RE.search(norm):
                blocks.append((norm, False))
        if not blocks:
            raise AnalyzerError(422, "متنی در FB2 پیدا نشد.")
        chapters.append({"title": meta["title"], "blocks": blocks})

    return _build_response(meta=meta, chapters_data=chapters,
                           source="headings" if len(chapters) > 1 else "single",
                           cover=None, wpm=wpm, wpp=wpp)


def analyze_epub(data: bytes, wpm: int, wpp: int) -> dict:
    validate_epub(data)
    try:
        book = epub.read_epub(io.BytesIO(data), {"ignore_ncx": False})
    except Exception:
        raise AnalyzerError(422, "ساختار EPUB نامعتبر است و خوانده نشد.")
    try:
        chapters, source = analyze_chapters(book)
        meta = extract_metadata(book)
        cover = extract_cover(book)
    except AnalyzerError:
        raise
    except RecursionError:
        raise AnalyzerError(422, "ساختار HTML کتاب بیش از حد تو در تو است.")
    except Exception:
        logger.exception("Text extraction failed")
        raise AnalyzerError(500, "استخراج متن از کتاب با خطا مواجه شد.")
    return _build_response(meta=meta, chapters_data=chapters, source=source,
                           cover=cover, wpm=wpm, wpp=wpp)


def analyze_file(data: bytes, filename: str, wpm: int, wpp: int) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    dispatch = {"epub": analyze_epub, "txt": analyze_txt, "docx": analyze_docx,
                "pdf": analyze_pdf, "fb2": analyze_fb2}
    fn = dispatch.get(ext)
    if fn is None:
        raise AnalyzerError(415, f"فرمت پشتیبانی نمی‌شود. فرمت‌های مجاز: {', '.join(sorted(SUPPORTED_FORMATS))}")
    if ext == "epub":
        return fn(data, wpm, wpp)
    return fn(data, filename, wpm, wpp)


# ========================== 16. Response Builder =======================
def _build_response(meta: dict, chapters_data: list[dict], source: str,
                    cover: str | None, wpm: int, wpp: int) -> dict:
    total = dict.fromkeys(STAT_KEYS, 0)
    chapters_out = []
    all_text_parts: list[str] = []
    for i, ch in enumerate(chapters_data, 1):
        stats = analyze_blocks(ch["blocks"])
        for k in STAT_KEYS:
            total[k] += stats[k]
        all_text_parts.extend(t for t, _ in ch["blocks"])
        rt = round(stats["words"] / wpm, 1) if wpm else 0
        chapters_out.append({
            "index": i, "title": ch["title"] or f"بخش {i}",
            "words": stats["words"], "letters": stats["letters"],
            "paragraphs": stats["paragraphs"], "sentences": stats["sentences"],
            "reading_time_minutes": rt,
        })

    words, paragraphs, sentences = total["words"], total["paragraphs"], total["sentences"]
    ratio = lambda a, b: round(a / b, 2) if b else 0  # noqa: E731

    detected = detect_language(" ".join(all_text_parts))

    return {
        "success": True,
        "book": {**meta, "detected_language": detected},
        "cover": cover,
        "chapter_source": source,
        "statistics": {
            "words": words,
            "letters": total["letters"],
            "letters_with_spaces": total["letters"] + total["spaces"],
            "characters": total["characters"],
            "characters_without_spaces": total["characters_without_spaces"],
            "characters_without_spaces_and_punctuation": total["characters_clean"],
            "paragraphs": paragraphs,
            "sentences": sentences,
            "chapters": len(chapters_out),
            "average_word_length": ratio(total["letters"], words),
            "average_sentence_length": ratio(total["paragraph_words"], sentences),
            "average_paragraph_words": ratio(total["paragraph_words"], paragraphs),
            "reading_time_minutes": round(words / wpm, 1),
            "estimated_pages": math.ceil(words / wpp),
            "words_per_minute": wpm,
            "words_per_page": wpp,
        },
        "chapters": chapters_out,
    }


# ============================ 17. API Routes ===========================
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/analyze":
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_UPLOAD_SIZE + (1 << 20):
            return error_response(413, f"حجم فایل بیشتر از {MAX_UPLOAD_SIZE // (1024 * 1024)} مگابایت است.")
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return error_response(400, "درخواست نامعتبر است.")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return error_response(500, "خطای داخلی سرور. لطفاً بعداً دوباره تلاش کنید.")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    return HTMLResponse(PAGE_HTML)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


@app.post("/api/analyze")
async def analyze(file: UploadFile | None = File(None),
                  words_per_minute: int = Form(DEFAULT_WORDS_PER_MINUTE),
                  words_per_page: int = Form(DEFAULT_WORDS_PER_PAGE)):
    if file is None or not (file.filename or "").strip():
        return error_response(400, "فایلی انتخاب نشده است.")
    fname = file.filename
    ext = "." + fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
    if ext not in SUPPORTED_FORMATS:
        return error_response(415, f"فرمت پشتیبانی نمی‌شود. مجاز: {', '.join(sorted(SUPPORTED_FORMATS))}")
    try:
        data = await file.read(MAX_UPLOAD_SIZE + 1)
    finally:
        await file.close()
    if len(data) > MAX_UPLOAD_SIZE:
        return error_response(413, f"حجم فایل بیشتر از {MAX_UPLOAD_SIZE // (1024 * 1024)} مگابایت است.")
    if not data:
        return error_response(400, "فایل انتخاب‌شده خالی است.")
    try:
        result = await asyncio.to_thread(
            analyze_file, data, fname,
            nonneg_int(words_per_minute, DEFAULT_WORDS_PER_MINUTE, 5000),
            nonneg_int(words_per_page, DEFAULT_WORDS_PER_PAGE, 10000))
    except AnalyzerError as exc:
        return error_response(exc.status, exc.message)
    except Exception:
        logger.exception("Analyze failed")
        return error_response(500, "خطای داخلی سرور. لطفاً بعداً دوباره تلاش کنید.")
    return result


# ========================= 18. Application Startup ======================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)