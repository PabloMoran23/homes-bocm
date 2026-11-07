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

SOURCE = 'https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-san-bartolome'
NAME = 'San Bartolomé'
INE = '35018'
SLUG = 'san-bartolome'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)


def parse_projects(payload):
    if not payload.get('success'):
        raise ValueError('SITCAN package API failed')
    data=payload['result']
    if data.get('name') != 'planeamiento-urbanistico-de-san-bartolome':
        raise ValueError('Wrong municipality dataset')
    rows=[]
    for resource in data.get('resources',[]):
        title=resource.get('name','')
        url=resource.get('url','')
        if resource.get('format','').upper() != 'HTML' or not title.startswith('Aprobación Definitiva') or 'San Bartolomé' not in title:
            continue
        if not re.match(r'https?://geobdp\.grafcan\.es/core/documentos/\d+/$',url):
            continue
        row=record(title,url,origen='registro_oficial_sitcan',fase='aprobación definitiva',
                   url_documento=url,resource_id=resource['id'])
        row['source']='gobierno_canarias'
        dates=re.findall(r'(\d{2})/(\d{2})/(\d{4})',title)
        row['fechas_publicacion']=[date(int(y),int(m),int(d)).isoformat() for d,m,y in dates]
        if len(set(row['fechas_publicacion']))==1:
            row['fecha_publicacion']=row['fechas_publicacion'][0]
        rows.append(row)
    return rows

class SanBartolomeAyuntamientoAdapter(AyuntamientoAdapter):
    parse_projects = staticmethod(parse_projects)

    def backfill_proyectos(self, out_jsonl: Path):
        req = Request(quote(SOURCE, safe=':/?=&%'), headers={'User-Agent': 'homes-municipal-research/1.0'})
        with build_opener(HTTPCookieProcessor(CookieJar())).open(req, timeout=30) as response:
            raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError('Municipal response too large')
            html = raw.decode(response.headers.get_content_charset() or 'utf-8')
        rows = parse_projects(json.loads(html))
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
