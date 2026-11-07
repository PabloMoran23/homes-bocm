"""Planning consultations discovered from the municipal participation inventory."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin,urlparse,parse_qs
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

class HuercalOveraAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://www.huercal-overa.es/Servicios/cmsdipro/index.nsf/informacion.xsp?documentId=9DF06E8926783D90C12581300029329D&p=huercal-overa'
    @classmethod
    def discover(cls,html):
        links={}
        for a in BeautifulSoup(html,'html.parser').select('a[href]'):
            title=a.get_text(' ',strip=True)
            if not re.search(r'consulta p[uú]blica',title,re.I):continue
            if not re.search(r'PGOU|plan general|estudio de detalle|plan de reforma interior',title,re.I):continue
            url=urljoin(cls.SOURCE,a['href']);query=parse_qs(urlparse(url).query);docid=query.get('documentId',[''])[0]
            if not docid or query.get('p')!=['huercal-overa']:continue
            if urlparse(url).hostname not in {'www.huercal-overa.es','www.dipalme.org'}:continue
            links[docid]=url
        if not links or len(links)>40:raise ValueError('Missing or unexpectedly large consultation inventory')
        return links
    @staticmethod
    def parse_detail(html,url,docid):
        soup=BeautifulSoup(html,'html.parser');h=soup.find('h2')
        if not h:raise ValueError('Missing municipal consultation heading')
        title=h.get_text(' ',strip=True)
        content=soup.select_one('form.xspForm')
        if content is None:raise ValueError('Missing municipal content form')
        docs=[{'titulo':a.get_text(' ',strip=True),'url':urljoin(url,a['href'])} for a in content.select('a[href]')
              if '$file/' in a['href']]
        description=content.select_one('[id$="teletipo_Texto1"]')
        text=description.get_text(' ',strip=True) if description else ''
        if not docs and len(text)<200:raise ValueError(f'No substantive proceeding content: {title}')
        innovation=re.search(r'innovaci[oó]n\s*(?:n[uú]mero|n[º°o.]*)?\s*(\d+)',title,re.I)
        key='innovacion-'+innovation.group(1) if innovation else docid.lower()
        return key,{'id':'huercal-overa-proy-'+key,'municipio':'Huércal-Overa','titulo':title,
                    'tipo':'modificacion_pgou' if innovation else 'planeamiento_urbanistico','fecha':None,
                    'url':url,'descripcion':text or None,'descripcion_source_url':url,'source':'ayuntamiento','origen':'consulta_planeamiento','documentos':docs,'source_urls':[url]}
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-huercal-overa/1.0'});r.raise_for_status();return r.text
        rows={}
        for docid,url in self.discover(fetch(self.SOURCE)).items():
            time.sleep(.35);key,row=self.parse_detail(fetch(url),url,docid)
            if key in rows:
                rows[key]['documentos'].extend(row['documentos']);rows[key]['source_urls'].append(url)
            else:rows[key]=row
        return self._write(out_jsonl,list(rows.values()))
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
