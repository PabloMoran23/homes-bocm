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

SOURCE = 'https://torredembarra.cat/avan%C3%A7dePOUM'
NAME = 'Torredembarra'
INE = '43153'
SLUG = 'torredembarra'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)

def parse_projects(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.find('main')
    if main is None or not any(h.get_text(' ', strip=True) == 'Avanç de POUM' for h in main.select('h1')):
        raise ValueError('Expected current POUM instrument page missing')
    docs = {}
    for a in main.select('a[href]'):
        url = urljoin(SOURCE, a['href'])
        if '/sites/default/files/' in url and url.lower().endswith('.pdf'):
            docs[url] = {'titulo':a.get_text(' ', strip=True), 'url':url}
    if not docs:
        return []
    section = next((h for h in main.select('h2,h3,h4,p') if h.get_text(' ',strip=True).startswith('En quin punt ens trobem')), None)
    description = ''
    if section:
        paragraphs = []
        # Drupal renders this section label as p > strong within ul > li.
        container = section.find_parent('ul') or section
        for sibling in container.next_siblings:
            if getattr(sibling, 'name', None) in ('h2','h3','h4','ul','ol'):
                break
            if hasattr(sibling, 'get_text'):
                paragraphs.append(sibling.get_text(' ', strip=True))
        description = ' '.join(paragraphs)
    return [record('Avanç de POUM de Torredembarra', SOURCE,
        documentos=list(docs.values()), descripcion=description,
        coverage='Current municipal POUM preparation page and published documents only')]

class TorredembarraAyuntamientoAdapter(AyuntamientoAdapter):
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
