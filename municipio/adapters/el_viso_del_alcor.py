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

SOURCE = 'https://www.elvisodelalcor.org/ayuntamiento/pgou/'
NAME = 'El Viso del Alcor'
INE = '41102'
SLUG = 'el-viso-del-alcor'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)


def parse_projects(html):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    rows=[]
    for li in soup.find_all('li'):
        label=li.find('p',recursive=False)
        nested=li.find('ul',recursive=False)
        if not label or not nested or label.find('a') or any(x.find('ul',recursive=False) for x in nested.find_all('li',recursive=False)):
            continue
        links=[urljoin(SOURCE,a['href']) for a in nested.select('a[href]') if '/galeriaFicheros/pgou/' in a['href'] and a['href'].lower().endswith('.pdf')]
        if not links:
            continue
        parts=[]
        for ancestor in reversed([li]+list(li.find_parents('li'))):
            p=ancestor.find('p',recursive=False)
            if p:
                t=p.get_text(' ',strip=True)
                if not t.startswith('PLANEAMIENTO'):
                    parts.append(t)
        title=' — '.join(parts)
        rows.append(record(title,title,documentos=list(dict.fromkeys(links)),url_documento=links[0],origen='inventario_planeamiento'))
    return rows

class ElVisoDelAlcorAyuntamientoAdapter(AyuntamientoAdapter):
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
