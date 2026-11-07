"""Municipal planning instruments and their grouped documentation in A Estrada."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

class AEstradaAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://aestrada.gal/urbanismo/'
    @classmethod
    def discover(cls,html):
        rows={}
        for a in BeautifulSoup(html,'html.parser').select('a[href]'):
            title=a.get_text(' ',strip=True);url=urljoin(cls.SOURCE,a['href'])
            if not re.match(r'^(?:PXOM$|Plan Especial\b|Plan parcial\b|Estudo de detalle\b)',title,re.I):continue
            if urlparse(url).hostname!='aestrada.gal':continue
            rows.setdefault(url,title)
        if not rows or len(rows)>30:raise ValueError('Missing or oversized municipal plan inventory')
        return rows
    @staticmethod
    def documents(html,url):
        docs={}
        for a in BeautifulSoup(html,'html.parser').select('a[href]'):
            link=urljoin(url,a['href']);parsed=urlparse(link)
            if parsed.hostname!='aestrada.gal' or not re.search(r'\.(?:pdf|zip|rar)$',parsed.path,re.I):continue
            label=a.get_text(' ',strip=True)
            if label or link not in docs:docs[link]={'titulo':label,'url':link}
        return docs
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-a-estrada/1.0'});r.raise_for_status();return r.content
        inventory=self.discover(fetch(self.SOURCE));rows=[]
        for url,title in inventory.items():
            time.sleep(.35);html=fetch(url);soup=BeautifulSoup(html,'html.parser')
            headings=[h.get_text(' ',strip=True) for h in soup.select('h2')]
            if not any(re.match(r'^(?:PXOM$|Plan Especial\b|Plan parcial\b|Estudo de detalle\b)',h,re.I) for h in headings):
                raise ValueError('Missing named planning instrument heading')
            docs=self.documents(html,url);sources=[url]
            if not docs:
                # Some instrument inventories link a document subpage rather
                # than the binary. Follow only labelled plan/compensation pages,
                # never the shared navigation to other instrument inventories.
                children=set()
                for a in soup.select('a[href]'):
                    link=urljoin(url,a['href']);label=a.get_text(' ',strip=True)
                    if link in inventory or urlparse(link).hostname!='aestrada.gal':continue
                    if re.match(r'^(?:Plan Parcial\b|Estatutos e bases)',label,re.I):children.add(link)
                if len(children)>10:raise ValueError('Unexpected child document inventory size')
                for link in sorted(children):time.sleep(.35);docs.update(self.documents(fetch(link),link));sources.append(link)
            if not docs:raise ValueError(f'No actual planning documents: {title}')
            rows.append({'id':'a-estrada-proy-'+hashlib.sha256(url.encode()).hexdigest()[:14],
                         'municipio':'A Estrada','titulo':title,'tipo':'planeamiento_urbanistico','fecha':None,
                         'url':url,'source':'ayuntamiento','origen':'instrumento_planeamiento_documentado',
                         'source_urls':sources,'documentos':list(docs.values())})
        return self._write(out_jsonl,rows)
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
