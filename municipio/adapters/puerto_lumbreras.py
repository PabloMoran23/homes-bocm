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

SOURCE = 'https://www.puertolumbreras.es/ayuntamiento/plangeneral/'
NAME = 'Puerto Lumbreras'
INE = '30033'
SLUG = 'puerto-lumbreras'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)

def parse_projects(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.page__content .c-content-box')
    title = next((h.get_text(' ', strip=True) for h in soup.select('h1') if 'Plan General de Ordenación Urbana de Puerto Lumbreras' in h.get_text()), None)
    if not content or not title:
        raise ValueError('Municipal PGOU document inventory missing')
    docs = {}
    for a in content.select('a[href]'):
        url = urljoin(SOURCE, a['href'])
        if '/ayuntamiento/wp-content/uploads/' in url and url.lower().endswith('.pdf'):
            docs[url] = {'titulo':a.get_text(' ', strip=True), 'url':url}
    if not docs:
        return []
    # Stage is supplied by the inventory; no assumption of definitive approval.
    stage = next((p.get_text(' ', strip=True) for p in content.select('p') if p.get_text(' ', strip=True).upper().startswith('APROBACIÓN')), '')
    return [record(title, SOURCE, documentos=list(docs.values()), estado=stage,
        coverage='Published PGOU document inventory only, grouped as one instrument')]

class PuertoLumbrerasAyuntamientoAdapter(AyuntamientoAdapter):
    parse_projects = staticmethod(parse_projects)

    def backfill_proyectos(self, out_jsonl: Path):
        req = Request(quote(SOURCE, safe=':/?=&%'), headers={'User-Agent': 'homes-municipal-research/1.0'})
        with build_opener(HTTPCookieProcessor(CookieJar())).open(req, timeout=30) as response:
            raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError('Municipal response too large')
            html = raw.decode(response.headers.get_content_charset() or 'utf-8')
        rows = parse_projects(html)
        if not rows:
            raise ValueError('No verified projects; source structure may have changed')
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
        return {'status':'ok','rows':len(rows),'source':SOURCE,'publication_ready':False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status':'disabled','rows':0,'reason':'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
