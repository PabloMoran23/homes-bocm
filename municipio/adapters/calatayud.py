"""Named instruments discovered from Calatayud's municipal urbanismo inventory."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

class CalatayudAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://www.calatayud.es/urbanismo'
    @classmethod
    def discover(cls,html):
        urls=[]
        for a in BeautifulSoup(html,'html.parser').select('a[href]'):
            title=a.get_text(' ',strip=True).lstrip('- ');url=urljoin(cls.SOURCE,a['href'])
            if re.match(r'^(?:plan general|plan especial|anteproyecto urbanizaci[oó]n)',title,re.I) and url.startswith(cls.SOURCE+'/'):
                if url not in urls:urls.append(url)
        if not urls or len(urls)>30:raise ValueError('Missing or oversized instrument inventory')
        return urls
    @staticmethod
    def parse_detail(html,url):
        soup=BeautifulSoup(html,'html.parser');h=soup.select_one('h1.titulo')
        if not h:raise ValueError('Missing instrument heading')
        title=h.get_text(' ',strip=True);docs={}
        if not re.match(r'^(?:plan general|plan especial|anteproyecto urbanizaci[oó]n)',title,re.I):raise ValueError('Unexpected instrument page')
        for a in soup.select('a[href]'):
            link=urljoin(url,a['href']);p=urlparse(link)
            if p.hostname!='www.calatayud.es' or not p.path.startswith('/admin/resources/planos/'):continue
            if not re.search(r'\.(?:pdf|zip|jpg|jpeg|png)$',p.path,re.I):continue
            label=a.get_text(' ',strip=True)
            if link not in docs or label.lower()!='archivos adjuntos':docs[link]={'titulo':label,'url':link}
        if not docs:raise ValueError('Instrument has no actual document inventory')
        return {'id':'calatayud-proy-'+hashlib.sha256(url.encode()).hexdigest()[:14],'municipio':'Calatayud',
                'titulo':title,'tipo':'urbanizacion' if title.lower().startswith('anteproyecto') else 'planeamiento_urbanistico',
                'fecha':None,'url':url,'source':'ayuntamiento','origen':'instrumento_planeamiento_documentado','documentos':list(docs.values())}
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-calatayud/1.0'});r.raise_for_status();return r.content
        rows=[]
        for url in self.discover(fetch(self.SOURCE)):time.sleep(.35);rows.append(self.parse_detail(fetch(url),url))
        return self._write(out_jsonl,rows)
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
