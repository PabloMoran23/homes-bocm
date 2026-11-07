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

SOURCE = 'https://www.calella.cat/ajuntament-seu-electronica/informacio-oficial/normativa/urbanisme/obra-publica'
NAME = 'Calella'
INE = '08035'
SLUG = 'calella'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)


def parse_projects(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for item in soup.select('li.article-item'):
        a = item.select_one('a[href]')
        if not a:
            continue
        url = urljoin(SOURCE, a['href'])
        if not url.startswith(SOURCE+'/') or not url.endswith('.html'):
            continue
        title = a.get_text(' ',strip=True)
        if not title:
            continue
        desc = item.select_one('.entradeta')
        row = record(title,url,origen='catalogo_obra_publica',descripcion=desc.get_text(' ',strip=True) if desc else None)
        row['url'] = url
        row['tipo'] = 'obra pública'
        # Listing periods are exposure windows, not approval/publication dates.
        rows.append(row)
    return rows

class CalellaAyuntamientoAdapter(AyuntamientoAdapter):
    parse_projects = staticmethod(parse_projects)

    def backfill_proyectos(self, out_jsonl: Path):
        import time
        from bs4 import BeautifulSoup
        rows = []
        pending = [SOURCE]
        visited = set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 20:
                raise ValueError('Catalogue pagination exceeds 20-page safety bound')
            visited.add(url)
            req = Request(url, headers={'User-Agent':'homes-municipal-research/1.0'})
            with urlopen(req,timeout=25) as response:
                raw = response.read(3_000_001)
                if len(raw)>3_000_000:
                    raise ValueError('Municipal response too large')
                html = raw.decode(response.headers.get_content_charset() or 'utf-8')
                rows.extend(parse_projects(html))
                for a in BeautifulSoup(html, 'html.parser').select('a[href]'):
                    next_url = urljoin(SOURCE, a['href'])
                    if re.fullmatch(re.escape(SOURCE)+r'\?pag=\d+', next_url) and next_url not in visited:
                        pending.append(next_url)
            time.sleep(0.15)
        rows = list({row['id']:row for row in rows}.values())
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
