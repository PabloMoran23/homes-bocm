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

SOURCE = 'https://albolote.org/wp-json/wp/v2/posts?search=obras&per_page=100'
NAME = 'Albolote'
INE = '18003'
SLUG = 'albolote'

def record(title, key, **extra):
    return dict(id=SLUG+'-proy-'+hashlib.sha256(key.encode()).hexdigest()[:14],
                municipio=NAME, codigo_ine=INE, titulo=title, tipo='planeamiento',
                fecha=None, fecha_aprob=None, fecha_publicacion=None, url=SOURCE,
                source='ayuntamiento', lat=None, lon=None, geometry=None,
                publication_ready=False, **extra)


def parse_projects(data):
    rows=[]
    for item in data:
        title=clean(item.get('title',{}).get('rendered',''))
        if not re.search(r'\bobras?\b',title,re.I) or not re.search(r'(asfalt|ampliaci|centro de salud|campo de f[uú]tbol|puente|reforma|carril bici|pabell[oó]n|construcci|remodel|rehabilit|urbaniz|instituto|colegio)',title,re.I):
            continue
        url=item.get('link','')
        if not url.startswith('https://albolote.org/'):
            continue
        row=record(title,str(item['id']),descripcion=clean(item.get('content',{}).get('rendered','')),origen='noticia_municipal_obra')
        row['url']=url
        row['tipo']='obra pública'
        value=item.get('date','')[:10]
        row['fecha_publicacion']=date.fromisoformat(value).isoformat() if value else None
        rows.append(row)
    return rows

class AlboloteAyuntamientoAdapter(AyuntamientoAdapter):
    parse_projects = staticmethod(parse_projects)

    def backfill_proyectos(self, out_jsonl: Path):
        rows=[]
        page=1
        total=1
        while page <= total:
            req=Request(SOURCE+'&page='+str(page),headers={'User-Agent':'homes-municipal-research/1.0'})
            with urlopen(req,timeout=25) as response:
                total=int(response.headers.get('X-WP-TotalPages','1'))
                if total>10:
                    raise ValueError('WP coverage exceeds 10-page safety bound')
                raw=response.read(6_000_001)
                if len(raw)>6_000_000:
                    raise ValueError('WP response exceeds size bound')
                rows.extend(parse_projects(json.loads(raw)))
            page+=1
        rows=list({r['id']:r for r in rows}.values())
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
