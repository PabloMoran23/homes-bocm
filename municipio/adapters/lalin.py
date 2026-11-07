"""Named planning instruments linked by Lalín's municipal transparency inventory."""
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

class LalinAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://portaltransparencia.lalin.gal/web/es/portal-de-transparencia'
    @classmethod
    def discover(cls,html):
        rows={}
        for a in BeautifulSoup(html,'html.parser').select('a[href]'):
            title=a.get_text(' ',strip=True);url=urljoin(cls.SOURCE,a['href'])
            if not re.match(r'^(?:Estudio de detalle|Plan especial|Modificaci[oó]n.*plan)',title,re.I):continue
            if urlparse(url).hostname!='www.xunta.gal' or '/dog/Publicados/' not in url:continue
            rows[url]={'id':'lalin-proy-'+hashlib.sha256(url.encode()).hexdigest()[:14],'municipio':'Lalín',
                       'titulo':title,'tipo':'estudio_detalle' if title.lower().startswith('estudio') else 'planeamiento_urbanistico',
                       'url':url,'source_url':cls.SOURCE,'source':'ayuntamiento','origen':'expediente_en_inventario_municipal'}
        if not rows or len(rows)>30:raise ValueError('Named instrument inventory missing or exceeds safety bound')
        return list(rows.values())
    @staticmethod
    def enrich(row,html):
        soup=BeautifulSoup(html,'html.parser');body=soup.select_one('#audioid')
        if body is None:raise ValueError('Official linked announcement has no substantive body')
        text=body.get_text(' ',strip=True)
        if 'Ayuntamiento de Lalín' not in text or not re.search(r'estudio de detalle|plan especial|planeamiento',text,re.I):
            raise ValueError('Linked announcement does not establish Lalín planning instrument')
        title=soup.title.get_text(' ',strip=True) if soup.title else ''
        match=re.search(r'DOG\s+\d+\s+del\s+(\d{2}/\d{2}/\d{4})',title)
        if not match:raise ValueError('No explicit publication date in official announcement heading')
        date=datetime.strptime(match.group(1),'%d/%m/%Y').date().isoformat()
        row.update({'fecha':date,'fecha_publicacion':date,'descripcion':text,'descripcion_source_url':row['url']})
        return row
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-lalin/1.0'});r.raise_for_status();return r.text
        rows=self.discover(fetch(self.SOURCE))
        for row in rows:time.sleep(.35);self.enrich(row,fetch(row['url']))
        return self._write(out_jsonl,rows)
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
