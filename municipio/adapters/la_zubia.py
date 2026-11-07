"""Municipal development-planning inventory: heritage catalogue and documents."""
import json
import re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

class LaZubiaAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://lazubia.es/urbanismo/planeamiento-de-desarrollo/'
    @classmethod
    def parse_projects(cls,html):
        body=BeautifulSoup(html,'html.parser').select_one('.singlepage .entry')
        if body is None:raise ValueError('Missing municipal planning inventory')
        text=body.get_text(' ',strip=True)
        match=re.search(r'Cat[aá]logo\s+de\s+Bienes\s+y\s+Espacios\s+Protegidos',text,re.I)
        if not match:raise ValueError('Named heritage planning instrument missing')
        docs=[]
        for a in body.select('a[href]'):
            if not re.search(r'\.pdf(?:\?|$)',a['href'],re.I):continue
            url=urljoin(cls.SOURCE,a['href'])
            if url not in {d['url'] for d in docs}:docs.append({'titulo':a.get_text(' ',strip=True),'url':url})
        if not docs:raise ValueError('Named planning instrument has no documents')
        return [{'id':'la-zubia-proy-catalogo-bienes-espacios-protegidos','municipio':'La Zubia',
                 'titulo':match.group(0),'tipo':'catalogo_patrimonio','fecha':None,'url':cls.SOURCE,
                 'source':'ayuntamiento','origen':'instrumento_planeamiento_documentado','documentos':docs}]
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        r=requests.get(self.SOURCE,timeout=25,headers={'User-Agent':'poc-bocm-la-zubia/1.0'});r.raise_for_status()
        return self._write(out_jsonl,self.parse_projects(r.text))
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
