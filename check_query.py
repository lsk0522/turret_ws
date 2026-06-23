import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

with open(ROOT / 'static/script.js', encoding='utf-8') as f: js = f.read()
with open(ROOT / 'templates/index.html', encoding='utf-8') as f: html = f.read()
q = set(re.findall(r"querySelector\(['\"](.*?)['\"]\)", js))
for s in q:
    if ' ' in s or ',' in s:
        continue
    if s.startswith('.'):
        if s[1:] not in html: print('MISSING CLASS:', s)
    elif s.startswith('#'):
        if s[1:] not in html: print('MISSING ID:', s)

