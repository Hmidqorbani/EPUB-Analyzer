"""EPUB Analyzer: تحلیل آماری فایل‌های EPUB (تک‌فایلی؛ Backend + Frontend).

اجرا:  uvicorn main:app --reload
"""
from __future__ import annotations

# ============================== 1. Imports ==============================
import asyncio
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

# ============================ 2. Configuration ==========================
APP_NAME = "EPUB Analyzer"
APP_VERSION = "1.0.0"

MAX_UPLOAD_SIZE = 100 * 1024 * 1024          # حداکثر حجم فایل آپلودی (بایت)
MAX_ZIP_ENTRIES = 5000                      # حداکثر تعداد Entry در ZIP
MAX_UNCOMPRESSED_SIZE = 400 * 1024 * 1024   # حداکثر مجموع حجم بعد از Extract
MAX_ENTRY_SIZE = 100 * 1024 * 1024          # حداکثر حجم هر Entry
MAX_COMPRESSION_RATIO = 1000                # نسبت فشرده‌سازی مشکوک (ZIP Bomb)
DEFAULT_WORDS_PER_MINUTE = 200
DEFAULT_WORDS_PER_PAGE = 300

logger = logging.getLogger("epub_analyzer")
warnings.filterwarnings("ignore", module="ebooklib")

# ======================== 3. FastAPI App Initialization =================
app = FastAPI(title=APP_NAME, version=APP_VERSION,
              description="Upload an EPUB file and get detailed text statistics.")


class AnalyzerError(Exception):
    """خطای قابل نمایش به کاربر همراه با کد HTTP."""

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
  var t = null;
  try { t = localStorage.getItem('theme'); } catch (e) {}
  if (t !== 'dark' && t !== 'light') {
    t = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.dataset.theme = t;
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
button { font: inherit; color: inherit; cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.icon-btn { width: 44px; height: 44px; border-radius: 14px; border: 1px solid var(--line); background: var(--glass);
  backdrop-filter: blur(10px); display: grid; place-items: center; }
.icon-btn svg { width: 20px; height: 20px; }
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
table { width: 100%; border-collapse: collapse; min-width: 560px; }
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
      <div><h1>EPUB Analyzer</h1><p>کلمه‌ها، حرف‌ها، جمله‌ها و فصل‌های کتاب EPUB را بشمارید.</p></div>
    </div>
    <button class="icon-btn" id="theme" type="button" aria-label="تغییر تم روشن/تیره" title="تغییر تم">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>
    </button>
  </header>

  <main>
    <section class="card drop" id="drop" aria-label="آپلود فایل EPUB">
      <svg class="book" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z"/><path d="M4 21.5A2.5 2.5 0 0 1 6.5 19H20v2H6.5"/><path d="M9 8h7M9 12h5"/></svg>
      <h2>فایل EPUB را اینجا رها کنید</h2>
      <p class="hint">یا از دکمه زیر برای انتخاب فایل استفاده کنید.</p>
      <div class="actions"><button class="btn" id="pick" type="button">انتخاب فایل</button></div>
      <p class="hint">فرمت پشتیبانی‌شده: EPUB. حداکثر حجم: __MAX_MB__ مگابایت.</p>
      <input type="file" id="input" accept=".epub,application/epub+zip" hidden>
      <div class="fileinfo" id="fileinfo" hidden>
        <div class="name" id="fname"></div>
        <div class="chips"><span class="chip" id="fsize"></span><span class="chip" id="fext"></span></div>
        <div class="status" id="status"></div>
        <div class="actions" style="justify-content:flex-start">
          <button class="btn ghost" id="again" type="button">تحلیل مجدد</button>
          <button class="btn ghost" id="other" type="button">انتخاب فایل دیگر</button>
        </div>
      </div>
    </section>
    <div class="error" id="error" role="alert" hidden><span id="errmsg"></span><button class="btn" id="retry" type="button">تلاش مجدد</button></div>

    <div id="results" hidden>
      <section class="card"><h2>اطلاعات کتاب</h2><dl class="meta" id="meta"></dl></section>
      <section><div class="grid" id="stats"></div></section>
      <section class="card"><h2>آمار تکمیلی</h2><div class="grid" id="extra"></div>
        <p class="note" id="note"></p></section>
      <section class="card"><h2>آمار فصل‌ها</h2>
        <div class="tablewrap"><table><thead><tr>
          <th scope="col">#</th><th scope="col">عنوان فصل</th>
          <th scope="col" id="wordsTh" aria-sort="none"><button type="button" id="sortWords" title="مرتب‌سازی بر اساس تعداد کلمات">کلمات <span id="arrow">⇅</span></button></th>
          <th scope="col">حروف</th><th scope="col">پاراگراف‌ها</th><th scope="col">جمله‌ها</th>
        </tr></thead><tbody id="rows"></tbody></table></div>
        <p class="note" id="chnote"></p></section>
    </div>
  </main>
  <footer>
    <a href="https://github.com/Hmidqorbani" target="_blank" rel="noopener noreferrer">Hmidqorbani</a>
    <span> — EPUB Analyzer، نسخه __VERSION__</span>
  </footer>
</div>

<script>
(() => {
  const MAX = __MAX_BYTES__;
  const $ = s => document.querySelector(s);
  const nf = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 });
  const fmt = n => (n === null || n === undefined) ? '—' : nf.format(n);
  const root = document.documentElement;
  let file = null, data = null, sortMode = 'none';

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

  // ----- Theme -----
  $('#theme').onclick = () => {
    const t = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = t;
    try { localStorage.setItem('theme', t); } catch (e) {}
  };

  // ----- Helpers -----
  const bytesText = b => b < 1024 ? fmt(b) + ' بایت' : b < 1048576 ? fmt(b / 1024) + ' کیلوبایت' : fmt(b / 1048576) + ' مگابایت';
  const showError = m => { $('#errmsg').textContent = m; $('#error').hidden = false; $('#retry').hidden = !file; };
  const hideError = () => { $('#error').hidden = true; };
  const setBusy = on => {
    $('#again').disabled = $('#other').disabled = $('#pick').disabled = on;
    $('#status').replaceChildren();
    if (on) {
      const s = document.createElement('span'); s.className = 'spin';
      $('#status').append(s, 'در حال تحلیل کتاب…');
    }
  };

  function setFile(f) {
    hideError();
    const ext = (f.name.includes('.') ? f.name.split('.').pop() : '').toLowerCase();
    if (ext !== 'epub') return showError('فقط فایل با پسوند EPUB پذیرفته می‌شود.');
    if (f.size === 0) return showError('فایل انتخاب‌شده خالی است.');
    if (f.size > MAX) return showError('حجم فایل بیشتر از ' + fmt(MAX / 1048576) + ' مگابایت است.');
    file = f;
    $('#fname').textContent = f.name;
    $('#fsize').textContent = 'حجم: ' + bytesText(f.size);
    $('#fext').textContent = 'پسوند: ' + ext.toUpperCase();
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
    let msg = 'ارتباط با سرور برقرار نشد. دوباره تلاش کنید.';
    try {
      const r = await fetch('/api/analyze', { method: 'POST', body: fd });
      let j = null;
      try { j = await r.json(); } catch (e) {}
      if (!r.ok || !j || !j.success) { msg = (j && j.error) || 'تحلیل فایل انجام نشد.'; throw new Error(); }
      data = j; render();
      $('#status').textContent = 'تحلیل کامل شد.';
      $('#results').hidden = false;
      $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      $('#status').replaceChildren(); $('#results').hidden = true;
      showError(msg);
    } finally {
      $('#again').disabled = $('#other').disabled = $('#pick').disabled = false;
      if ($('#status').firstChild && $('#status').querySelector('.spin')) $('#status').replaceChildren();
    }
  }

  // ----- Rendering -----
  function render() {
    const b = data.book, s = data.statistics;
    const meta = $('#meta'); meta.replaceChildren();
    [['عنوان', b.title], ['نویسنده', b.author], ['ناشر', b.publisher], ['زبان', b.language],
     ['شناسه', b.identifier], ['تاریخ انتشار', b.publication_date], ['توضیحات', b.description, true]].forEach(([k, v, wide]) => {
      const row = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = k; dd.textContent = v || 'ثبت نشده';
      if (!v) dd.className = 'none';
      if (wide) row.className = 'wide';
      row.append(dt, dd); meta.append(row);
    });
    const cards = [
      ['words', 'Words', 'کلمات', s.words], ['chars', 'Characters', 'کاراکترها (با فاصله)', s.characters],
      ['nospace', 'Characters Without Spaces', 'کاراکترها بدون فاصله', s.characters_without_spaces],
      ['letters', 'Letters', 'حروف', s.letters], ['lettersws', 'Letters With Spaces', 'حروف با فاصله', s.letters_with_spaces],
      ['paragraphs', 'Paragraphs', 'پاراگراف‌ها', s.paragraphs], ['sentences', 'Sentences', 'جمله‌ها', s.sentences],
      ['chapters', 'Chapters', 'فصل‌ها', s.chapters]];
    const grid = $('#stats'); grid.replaceChildren();
    cards.forEach(([ic, en, fa, v]) => {
      const el = document.createElement('div'); el.className = 'card stat'; el.title = en;
      el.innerHTML = '<div class="ico">' + svg(ICONS[ic]) + '</div><div><div class="val"></div><div class="lbl"></div></div>';
      el.querySelector('.val').textContent = fmt(v); el.querySelector('.lbl').textContent = fa;
      grid.append(el);
    });
    renderExtra(); renderRows();
    $('#chnote').textContent = data.chapter_source === 'toc'
      ? 'فصل‌ها بر اساس فهرست مطالب (TOC) کتاب و ترتیب خوانش (Spine) تعیین شده‌اند.'
      : 'این کتاب فصل‌بندی مشخصی ندارد؛ هر بخش متنی معتبر به‌عنوان یک فصل گزارش شده است.';
  }

  function mini(label, value, input) {
    const el = document.createElement('div'); el.className = 'mini';
    el.innerHTML = '<div class="val"></div><div class="lbl"></div>';
    el.querySelector('.val').textContent = value; el.querySelector('.lbl').textContent = label;
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
      mini('میانگین طول کلمه (حرف)', fmt(s.average_word_length)),
      mini('میانگین طول جمله (کلمه)', fmt(s.average_sentence_length)),
      mini('میانگین کلمات هر پاراگراف', fmt(s.average_paragraph_words)),
      mini('کاراکتر بدون فاصله و علائم', fmt(s.characters_without_spaces_and_punctuation)),
      mini('زمان مطالعه', '', field('wpm', 'کلمه در دقیقه', wpm, 5000)),
      mini('تعداد صفحات تخمینی', '', field('wpp', 'کلمه در صفحه', wpp, 10000)));
    ex.children[4].id = 'rt'; ex.children[5].id = 'pg';
    updateEstimates();
  }
  function updateEstimates() {
    const w = data.statistics.words;
    const wpm = Math.max(1, +$('#wpm').value || 200), wpp = Math.max(1, +$('#wpp').value || 300);
    const total = Math.round(w / wpm), h = Math.floor(total / 60), m = total % 60;
    $('#rt .val').textContent = total === 0 ? 'کمتر از ۱ دقیقه' : (h ? fmt(h) + ' ساعت' : '') + (h && m ? ' و ' : '') + (m ? fmt(m) + ' دقیقه' : '');
    $('#pg .val').textContent = fmt(Math.ceil(w / wpp));
    $('#note').textContent = 'زمان مطالعه = کل کلمات ÷ سرعت مطالعه. صفحه‌های EPUB ثابت نیستند و تعداد صفحات فقط یک تخمین بر اساس تعداد کلمه است.';
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
      [fmt(c.index), c.title, fmt(c.words), fmt(c.letters), fmt(c.paragraphs), fmt(c.sentences)].forEach((t, i) => {
        const td = document.createElement('td'); td.textContent = t; if (i === 1) td.className = 'title'; tr.append(td);
      });
      tb.append(tr);
    });
  }
  $('#sortWords').onclick = () => { sortMode = sortMode === 'none' ? 'desc' : sortMode === 'desc' ? 'asc' : 'none'; renderRows(); };

  // ----- Upload events -----
  const input = $('#input'), drop = $('#drop');
  $('#pick').onclick = $('#other').onclick = () => input.click();
  $('#again').onclick = $('#retry').onclick = analyze;
  input.onchange = () => { if (input.files[0]) setFile(input.files[0]); input.value = ''; };
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
  ['dragover', 'drop'].forEach(ev => window.addEventListener(ev, e => e.preventDefault()));
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
    """مقدار تنظیمات را به بازه معتبر محدود می‌کند."""
    return default if value is None or value < 1 else min(value, upper)


def clean_str(value) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


# ========================== 8. EPUB Validation ==========================
_FONT_OBFUSCATION = ("http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC")


def validate_epub(data: bytes) -> None:
    """ساختار ZIP و EPUB را بدون استخراج روی دیسک بررسی می‌کند."""
    buf = io.BytesIO(data)
    if not zipfile.is_zipfile(buf):
        raise AnalyzerError(422, "این فایل یک EPUB معتبر نیست (ساختار ZIP تشخیص داده نشد).")
    try:
        with zipfile.ZipFile(buf) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise AnalyzerError(422, "تعداد فایل‌های داخل EPUB غیرعادی است و پردازش نمی‌شود.")
            total = 0
            for info in infos:
                parts = info.filename.replace("\\", "/").split("/")
                if info.filename.startswith(("/", "\\")) or ".." in parts:
                    raise AnalyzerError(422, "مسیرهای نامعتبر داخل فایل EPUB وجود دارد.")
                if info.flag_bits & 0x1:
                    raise AnalyzerError(422, "فایل رمزگذاری‌شده است و قابل پردازش نیست.")
                if info.file_size > MAX_ENTRY_SIZE:
                    raise AnalyzerError(422, "حجم یکی از فایل‌های داخل EPUB بیش از حد مجاز است.")
                if info.file_size > (1 << 20) and info.compress_size and \
                        info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                    raise AnalyzerError(422, "فایل مشکوک به ZIP Bomb است و پردازش نمی‌شود.")
                total += info.file_size
            if total > MAX_UNCOMPRESSED_SIZE:
                raise AnalyzerError(422, "حجم محتوای EPUB پس از باز شدن بیش از حد مجاز است.")
            names = {i.filename for i in infos}
            if "META-INF/container.xml" not in names:
                raise AnalyzerError(422, "ساختار EPUB نامعتبر است (فایل container.xml یافت نشد).")
            if "mimetype" in names and zf.open("mimetype").read(64).strip() != b"application/epub+zip":
                raise AnalyzerError(422, "نوع MIME فایل با EPUB مطابقت ندارد.")
            if "META-INF/encryption.xml" in names:
                algos = re.findall(r'Algorithm="([^"]+)"', zf.read("META-INF/encryption.xml").decode("utf-8", "ignore"))
                if any(a not in _FONT_OBFUSCATION for a in algos):
                    raise AnalyzerError(422, "این کتاب با DRM محافظت شده و قابل پردازش نیست.")
    except AnalyzerError:
        raise
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, OSError, ValueError):
        raise AnalyzerError(422, "فایل EPUB خراب است یا قابل خواندن نیست.")


# ========================= 9. EPUB Extraction ===========================
BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "blockquote", "section", "article", "aside", "tr", "td", "th", "table",
              "dd", "dt", "dl", "figcaption", "figure", "pre", "header", "footer", "main", "body", "caption", "hr",
              "h1", "h2", "h3", "h4", "h5", "h6"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS = {"script", "style", "svg", "math", "img", "head", "nav", "audio", "video", "canvas", "object", "iframe"}
NAV_TYPES = {"toc", "landmarks", "page-list"}
NON_CHAPTER_TYPES = {"toc", "landmarks", "cover", "titlepage", "halftitlepage", "copyright-page"}


def _types(tag: Tag) -> set[str]:
    raw = f"{tag.get('epub:type') or ''} {tag.get('role') or ''}"
    return {t.removeprefix("doc-") for t in raw.split()}


def _flush(out: list, buf: list, heading: bool) -> None:
    if buf:
        text = normalize_text("".join(buf))
        buf.clear()
        if WORD_RE.search(text):
            out.append((text, heading))


def _walk(node, out: list, buf: list, heading: bool) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            if not isinstance(child, PreformattedString):  # کامنت، CDATA، Doctype حذف می‌شوند
                buf.append(str(child))
        elif isinstance(child, Tag):
            name = (child.name or "").lower()
            if name in SKIP_TAGS or _types(child) & NAV_TYPES:
                continue
            if name == "br":
                buf.append(" ")
            elif name in BLOCK_TAGS:
                inner = heading or name in HEADING_TAGS
                _flush(out, buf, heading)
                _walk(child, out, buf, inner)
                _flush(out, buf, inner)
            else:
                _walk(child, out, buf, heading)


def extract_blocks(soup: BeautifulSoup) -> list[tuple[str, bool]]:
    """بلوک‌های متنی سند را به‌صورت (متن، آیا_عنوان_است) و به ترتیب خوانش برمی‌گرداند."""
    out: list[tuple[str, bool]] = []
    buf: list[str] = []
    _walk(soup, out, buf, False)
    _flush(out, buf, False)
    return out


def is_non_chapter_doc(soup: BeautifulSoup, blocks: list[tuple[str, bool]]) -> bool:
    """Navigation، فهرست مطالب، جلد و صفحات مشابه را تشخیص می‌دهد."""
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


# ========================= 10. Text Normalization =======================
_STRIP = dict.fromkeys(map(ord, "\u00ad\u200b\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                                "\u2066\u2067\u2068\u2069\ufeff\u0640"))


def normalize_text(text: str) -> str:
    """NFKC، حذف نویسه‌های نامرئی (به‌جز نیم‌فاصله ZWNJ) و کشیده، و فشرده‌سازی فاصله‌ها."""
    text = unicodedata.normalize("NFKC", text).translate(_STRIP)
    return re.sub(r"\s+", " ", text).strip()


# ============================ 11. Word Counting =========================
# کلمه = دنباله‌ای از حروف/ارقام یونیکد (به‌همراه اعراب)، که با نیم‌فاصله (ZWNJ)، آپوستروف یا خط‌تیره
# به هم می‌پیوندند ("کتاب‌خوانی"، "well-known"، "don't")؛ همچنین اعداد اعشاری/هزارگان ("3.14"، "۱٬۲۰۰").
_MARKS = "\u0300-\u036f\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed"
_W = rf"(?:[^\W_]|[{_MARKS}])"
WORD_RE = re.compile(rf"\d+(?:[.,٫٬]\d+)+(?![^\W_])|{_W}+(?:[\u200c'’\-\u2010]{_W}+)*")


def count_words(text: str) -> int:
    return sum(1 for _ in WORD_RE.finditer(text))


# ========================= 12. Character Counting =======================
def count_characters(text: str) -> dict[str, int]:
    """متن باید از قبل نرمال شده باشد (تنها فاصله باقی‌مانده، space معمولی است)."""
    letters = sum(map(str.isalpha, text))
    spaces = text.count(" ")
    punct = sum(1 for ch in text if not ch.isalnum() and unicodedata.category(ch)[0] in "PS")
    return {"letters": letters, "spaces": spaces, "characters": len(text),
            "characters_without_spaces": len(text) - spaces,
            "characters_clean": len(text) - spaces - punct}


# ========================== 13. Sentence Counting =======================
_SENT_END = re.compile(r"([.!?؟۔…]+)[\"'”’»)\]]*(?=\s|$)")
_ABBREV = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs"}
_LAST_WORD = re.compile(r"([^\W\d_]+)$")


def count_sentences(text: str) -> int:
    """هر گروه علائم پایان‌جمله (مثل ?! یا ...) یک مرز است؛ مخفف‌ها (Dr.) و حروف اول (J.) مرز نیستند."""
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


# ========================= 14. Paragraph Counting =======================
STAT_KEYS = ("words", "letters", "spaces", "characters", "characters_without_spaces", "characters_clean",
             "paragraphs", "sentences", "paragraph_words")


def analyze_blocks(blocks: list[tuple[str, bool]]) -> dict[str, int]:
    """عنوان‌ها در کلمه/حرف/کاراکتر لحاظ می‌شوند ولی پاراگراف و جمله به‌حساب نمی‌آیند."""
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


# =========================== 15. Chapter Analysis =======================
def _norm_href(href: str | None) -> str:
    return posixpath.normpath(unquote((href or "").split("#")[0])).lstrip("./") if href else ""


def toc_leaves(items) -> list[tuple[str, str]]:
    """برگ‌های فهرست مطالب (عنوان، مسیر) به ترتیب."""
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


def analyze_chapters(book: epub.EpubBook) -> tuple[list[dict], dict[str, int], str]:
    """سندهای Spine را به ترتیب پردازش و به فصل تبدیل می‌کند. خروجی: (فصل‌ها، جمع کل، منبع فصل‌بندی)."""
    docs, seen = [], set()
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
        if digest in seen:  # سند تکراری
            continue
        seen.add(digest)
        heading = next((t for t, h in blocks if h and len(t) <= 150), None)
        docs.append({"name": _norm_href(item.get_name()), "heading": heading, "stats": analyze_blocks(blocks)})
    if not docs:
        raise AnalyzerError(422, "در این EPUB محتوای متنی قابل‌خواندن پیدا نشد.")

    by_path = {d["name"]: d for d in docs}
    by_base: dict[str, list] = {}
    for d in docs:
        by_base.setdefault(posixpath.basename(d["name"]), []).append(d)
    starts: dict[int, str] = {}  # شناسه سند -> عنوان فصل در TOC
    for title, href in toc_leaves(book.toc or []):
        path = _norm_href(href)
        doc = by_path.get(path) or next((x for p, x in by_path.items() if p.endswith("/" + path)), None)
        if doc is None and len(by_base.get(posixpath.basename(path), [])) == 1:
            doc = by_base[posixpath.basename(path)][0]
        if doc is not None and id(doc) not in starts:
            starts[id(doc)] = title

    groups: list[dict] = []
    source = "toc" if starts else "spine"
    pending: list[dict] = []
    for d in docs:
        if source == "spine" or id(d) in starts:
            title = starts.get(id(d)) or d["heading"] or f"بخش {len(groups) + 1}"
            groups.append({"title": title, "parts": pending + [d]})
            pending = []
        elif groups:
            groups[-1]["parts"].append(d)
        else:
            pending.append(d)  # متن قبل از اولین فصل TOC به فصل اول می‌پیوندد

    total = dict.fromkeys(STAT_KEYS, 0)
    chapters = []
    for i, g in enumerate(groups, 1):
        agg = dict.fromkeys(STAT_KEYS, 0)
        for part in g["parts"]:
            for k in STAT_KEYS:
                agg[k] += part["stats"][k]
        for k in STAT_KEYS:
            total[k] += agg[k]
        chapters.append({"index": i, "title": g["title"], "words": agg["words"], "letters": agg["letters"],
                         "paragraphs": agg["paragraphs"], "sentences": agg["sentences"]})
    return chapters, total, source


# ========================= 16. Metadata Extraction ======================
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


# ============================= 17. API Routes ===========================
def analyze_epub(data: bytes, words_per_minute: int, words_per_page: int) -> dict:
    """تحلیل کامل در حافظه (همگام؛ از طریق thread اجرا می‌شود)."""
    validate_epub(data)
    try:
        book = epub.read_epub(io.BytesIO(data), {"ignore_ncx": False})
    except Exception:
        raise AnalyzerError(422, "ساختار EPUB نامعتبر است و خوانده نشد.")
    try:
        chapters, t, source = analyze_chapters(book)
        meta = extract_metadata(book)
    except AnalyzerError:
        raise
    except RecursionError:
        raise AnalyzerError(422, "ساختار HTML کتاب بیش از حد تو در تو است.")
    except Exception:
        logger.exception("Text extraction failed")
        raise AnalyzerError(500, "استخراج متن از کتاب با خطا مواجه شد.")

    words, paragraphs, sentences = t["words"], t["paragraphs"], t["sentences"]
    ratio = lambda a, b: round(a / b, 2) if b else 0  # noqa: E731
    return {
        "success": True,
        "book": meta,
        "chapter_source": source,
        "statistics": {
            "words": words,
            "letters": t["letters"],
            "letters_with_spaces": t["letters"] + t["spaces"],
            "characters": t["characters"],
            "characters_without_spaces": t["characters_without_spaces"],
            "characters_without_spaces_and_punctuation": t["characters_clean"],
            "paragraphs": paragraphs,
            "sentences": sentences,
            "chapters": len(chapters),
            "average_word_length": ratio(t["letters"], words),
            "average_sentence_length": ratio(t["paragraph_words"], sentences),
            "average_paragraph_words": ratio(t["paragraph_words"], paragraphs),
            "reading_time_minutes": round(words / words_per_minute, 1),
            "estimated_pages": math.ceil(words / words_per_page),
            "words_per_minute": words_per_minute,
            "words_per_page": words_per_page,
        },
        "chapters": chapters,
    }


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """رد سریع درخواست‌های بزرگ بر اساس Content-Length، پیش از خواندن بدنه."""
    if request.method == "POST" and request.url.path == "/api/analyze":
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_UPLOAD_SIZE + (1 << 20):
            return error_response(413, f"حجم فایل بیشتر از {MAX_UPLOAD_SIZE // (1024 * 1024)} مگابایت است.")
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return error_response(400, "درخواست نامعتبر است. فایل و تنظیمات را بررسی کنید.")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return error_response(500, "خطای داخلی سرور. لطفاً بعداً دوباره تلاش کنید.")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    return HTMLResponse(PAGE_HTML)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": APP_NAME}


@app.post("/api/analyze")
async def analyze(file: UploadFile | None = File(None),
                  words_per_minute: int = Form(DEFAULT_WORDS_PER_MINUTE),
                  words_per_page: int = Form(DEFAULT_WORDS_PER_PAGE)):
    """فایل EPUB را دریافت و تحلیل می‌کند (فقط در حافظه؛ بدون ذخیره دائمی)."""
    if file is None or not (file.filename or "").strip():
        return error_response(400, "فایلی انتخاب نشده است.")
    if not file.filename.lower().endswith(".epub"):  # نام فایل هرگز به‌عنوان مسیر استفاده نمی‌شود
        return error_response(415, "فقط فایل‌های EPUB پذیرفته می‌شوند.")
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
            analyze_epub, data, nonneg_int(words_per_minute, DEFAULT_WORDS_PER_MINUTE, 5000),
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
