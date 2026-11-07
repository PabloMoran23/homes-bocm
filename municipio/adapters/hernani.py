"""Active municipal urban-planning notice inventory, with attached source documents."""
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

class HernaniAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://www.hernani.eus/es/urbanismo-medioambiente-vigor'
    @classmethod
    def parse_inventory(cls,html):
        soup=BeautifulSoup(html,'html.parser')
        for a in soup.select('a[href]'):
            if a.get_text(' ',strip=True).lower() in {'siguiente','next','hurrengoa'} and a['href'] not in {'','#'}:
                raise ValueError('Active inventory now paginated; extend crawler before accepting partial output')
        rows={}
        for block in soup.select('.titulo_fecha'):
            a=block.select_one('.titulo a[href]');d=block.select_one('.fecha')
            if not a:continue
            title=a.get_text(' ',strip=True);url=urljoin(cls.SOURCE,a['href'])
            if not re.match(r'^(?:PROYECTO DE REPARCELACI[OÓ]N|PLAN ESPECIAL|ESTUDIO DE DETALLE|MODIFICACI[OÓ]N)',title,re.I):continue
            match=re.search(r'/content/([^/?]+)',url)
            if not match or urlparse(url).hostname!='www.hernani.eus':continue
            date=datetime.strptime(d.get_text(strip=True),'%d·%m·%Y').date().isoformat() if d else None
            canonical=url.split('?')[0]
            rows[match.group(1)]={'id':'hernani-proy-'+match.group(1),'municipio':'Hernani','titulo':title,
                'tipo':'reparcelacion' if 'REPARCELACI' in title.upper() else 'planeamiento_urbanistico',
                'fecha':date,'fecha_publicacion':date,'url':canonical,'source':'ayuntamiento','origen':'expediente_urbanismo_vigente'}
        if not rows:raise ValueError('No supported active planning notices; review current inventory')
        if len(rows)>50:raise ValueError('Active notice inventory exceeds reviewed limit')
        return list(rows.values())
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-hernani/1.0'});r.raise_for_status();return r.text
        rows=self.parse_inventory(fetch(self.SOURCE))
        for row in rows:
            time.sleep(.35);soup=BeautifulSoup(fetch(row['url']),'html.parser');docs={}
            for a in soup.select('a[href]'):
                url=urljoin(row['url'],a['href'])
                if urlparse(url).hostname=='www.hernani.eus' and '/documents/' in urlparse(url).path:
                    docs.setdefault(url.split('?')[0],{'titulo':a.get_text(' ',strip=True),'url':url})
            if not docs:raise ValueError('Planning notice lacks source documents')
            row['documentos']=list(docs.values())
        return self._write(out_jsonl,rows)
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
