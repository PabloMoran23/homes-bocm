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

SOURCE = 'https://transparencia.archena.es/t/p/63-normativa-vigente-de-instrumentos-urbanisticos'
NAME = 'Archena'
INE = '30009'
SLUG = 'archena'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)


def parse_projects(html):
    rows = []
    for table in re.findall(r'<table\b[^>]*>(.*?)</table>', html, re.I|re.S):
        if 'B.O.R.M.' not in clean(table) or 'ACTUACIÓN' not in clean(table):
            continue
        for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table, re.I|re.S):
            cells = re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.I|re.S)
            if len(cells) != 2:
                continue
            title = clean(cells[0])
            if not ('Plan Parcial' in title or 'Normas Subsidiarias' in title):
                continue
            notices = clean(cells[1])
            dates = re.findall(r'\b(\d{2})\.(\d{2})\.(\d{4})\b', notices)
            if not dates:
                continue
            parsed_dates = [date(int(y), int(m), int(d)).isoformat() for d,m,y in dates]
            row = record(title, title, referencias_publicacion=notices,
                         fechas_publicacion=parsed_dates)
            # Some rows bundle a plan and modifications: preserve all dates,
            # without falsely assigning one date to the combined record.
            if len(parsed_dates) == 1:
                row['fecha_publicacion'] = parsed_dates[0]
            rows.append(row)
    return rows

class ArchenaAyuntamientoAdapter(AyuntamientoAdapter):
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
