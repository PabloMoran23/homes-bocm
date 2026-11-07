from __future__ import annotations
import hashlib
import json
import re
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, quote
from http.cookiejar import CookieJar
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from municipio.adapters.portal import AyuntamientoAdapter

def clean(value):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', value)).split())

SOURCE = 'https://www.lesfranqueses.cat/actualitat/noticies/'
NAME = 'Les Franqueses del Vallès'
INE = '08086'
SLUG = 'les-franqueses-del-valles'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)


def parse_projects(html, source_url=SOURCE):
    heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I|re.S)
    class Body(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.text = []
        def handle_starttag(self, tag, attrs):
            if tag == 'div':
                if self.depth:
                    self.depth += 1
                elif dict(attrs).get('class') == 'ddbbtext':
                    self.depth = 1
        def handle_endtag(self, tag):
            if tag == 'div' and self.depth:
                self.depth -= 1
        def handle_data(self, text):
            if self.depth:
                self.text.append(text)
    body = Body()
    body.feed(html)
    if not heading or not body.text:
        return []
    title, text = clean(heading[1]), ' '.join(' '.join(body.text).split())
    if 'modificació del planejament urbanístic' not in title.lower() or 'ha aprovat la modificació' not in text:
        return []
    row = record(title, source_url, descripcion=text, origen='noticia_municipal_proyecto', fase='aprobación comunicada')
    published = re.search(r'<div\b[^>]*class=["\']date["\'][^>]*>(.*?)</div>', html, re.I|re.S)
    if published:
        match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', clean(published[1]))
        months = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()
        if match and match[2] in months:
            row['fecha_publicacion'] = date(int(match[3]), months.index(match[2])+1, int(match[1])).isoformat()
    row['url'] = source_url
    # Boundary streets come from the actual article; no geocoding of town hall.
    boundary = re.search(r"l'illa compresa entre els carrers ([^.]+)", text)
    if boundary:
        row['ambito_descripcion'] = boundary[0]
    return [row]

class LesFranquesesDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    parse_projects = staticmethod(parse_projects)

    @staticmethod
    def discover_projects(html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        urls = []
        for a in soup.select('a[href]'):
            title = a.get_text(' ', strip=True)
            url = urljoin(SOURCE, a['href'])
            if (url.startswith(SOURCE) and url.endswith('.html')
                    and 'modificació del planejament urbanístic' in title.lower()):
                urls.append(url)
        return list(dict.fromkeys(urls))

    def backfill_proyectos(self, out_jsonl: Path):
        import time
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        def fetch(url):
            time.sleep(0.15)
            with opener.open(Request(url, headers={'User-Agent':'homes-municipal-research/1.0'}), timeout=20) as response:
                raw = response.read(3_000_001)
                if len(raw) > 3_000_000:
                    raise ValueError('Municipal response too large')
                return raw.decode(response.headers.get_content_charset() or 'utf-8')
        urls = []
        pages = min(16, max(1, int(self.config.get('max_listing_pages',16))))
        for page in range(1, pages+1):
            urls.extend(self.discover_projects(fetch(SOURCE+'?pag='+str(page))))
        rows = []
        unique_urls = list(dict.fromkeys(urls))
        if len(unique_urls) > 20:
            raise ValueError('More than 20 planning details discovered; refusing truncated results')
        for url in unique_urls:
            rows.extend(parse_projects(fetch(url), url))
        if not rows:
            raise ValueError('No verified planning projects in bounded news listing; coverage requires review')
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
        return {'status':'ok','rows':len(rows),'source':SOURCE,'listing_pages':pages,
                'coverage':'bounded_latest_news_pages','publication_ready':False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status':'disabled','rows':0,'reason':'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
