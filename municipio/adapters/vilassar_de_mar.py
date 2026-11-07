"""Named PGOU amendments and heritage plan in the municipal planning register."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter


class VilassarDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    # Explicit public HTTP endpoint: HTTPS currently has an incomplete certificate
    # chain. Do not silently disable TLS verification or downgrade other requests.
    SOURCE = 'http://www.vilassardemar.cat/seu-electronica/serveis-municipals/linea-de-servei/planejament-urbanistic'

    @classmethod
    def parse_projects(cls, html):
        soup = BeautifulSoup(html, 'html.parser')
        rows = []
        for item in soup.select('li'):
            heading = BeautifulSoup(str(item), 'html.parser').li
            for nested in heading.select('ul,ol'):
                nested.decompose()
            title = heading.get_text(' ', strip=True)
            if not re.match(r'^(?:MPGOU\b|Pla especial urbanístic\b)', title, re.I):
                continue
            docs = [{'titulo': a.get_text(' ', strip=True), 'url': urljoin(cls.SOURCE, a['href'])}
                    for a in item.select('a[href]') if re.search(r'\.pdf(?:\?|$)', a['href'], re.I)]
            if not docs:
                raise ValueError(f'Planning instrument has no linked documents: {title}')
            rows.append({'id': 'vilassar-de-mar-proy-' + hashlib.sha256(docs[0]['url'].encode()).hexdigest()[:14],
                         'municipio': 'Vilassar de Mar', 'titulo': title, 'fecha': None,
                         'tipo': 'modificacion_pgou' if title.startswith('MPGOU') else 'plan_especial',
                         'url': docs[0]['url'], 'source_url': cls.SOURCE, 'documentos': docs,
                         'source': 'ayuntamiento', 'origen': 'instrumento_planeamiento_documentado'})
        if not rows:
            raise ValueError('No named planning instruments found; review page layout')
        return rows

    @staticmethod
    def _write(path, rows):
        path=Path(path);path.parent.mkdir(parents=True, exist_ok=True)
        temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}

    def backfill_proyectos(self,out_jsonl):
        r=requests.get(self.SOURCE,timeout=25,headers={'User-Agent':'poc-bocm-vilassar-de-mar/1.0'});r.raise_for_status()
        return self._write(out_jsonl,self.parse_projects(r.text))
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
