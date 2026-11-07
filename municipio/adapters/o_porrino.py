"""Current municipal PXOM plan-sheet inventories, grouped by instrument/year."""
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter


class OPorrinoAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = 'https://oporrino.org/'

    @classmethod
    def inventory_urls(cls, html):
        urls=[]
        for a in BeautifulSoup(html,'html.parser').select('a[href]'):
            if not re.match(r'^PXOM\s+\d{4}\s+PLANOS',a.get_text(' ',strip=True),re.I):continue
            url=urljoin(cls.SOURCE,a['href'])
            if urlparse(url).hostname not in {'oporrino.org','www.oporrino.org'}:continue
            if url not in urls:urls.append(url)
        if not urls:raise ValueError('No municipal PXOM inventories found')
        if len(urls)>20:raise ValueError('Inventory count exceeded reviewed bound')
        return urls

    @classmethod
    def parse_inventory(cls,html,url):
        soup=BeautifulSoup(html,'html.parser');h=soup.find('h1')
        match=re.match(r'^PXOM\s+(\d{4})\s+PLANOS',h.get_text(' ',strip=True) if h else '',re.I)
        if not match:raise ValueError('Expected a named PXOM plan-sheet inventory')
        docs={}
        for a in soup.select('a[href]'):
            href=urljoin(url,a['href']);parsed=urlparse(href)
            if parsed.hostname not in {'oporrino.org','www.oporrino.org'}:continue
            if '/PXOM/' not in parsed.path or not parsed.path.lower().endswith('.pdf'):continue
            # Duplicate mobile/desktop blocks and http/https aliases are one sheet.
            docs.setdefault(parsed.path,{'titulo':a.get_text(' ',strip=True),'url':href})
        if not docs:raise ValueError('PXOM inventory contains no plan-sheet documents')
        return match.group(1),list(docs.values())

    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}

    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-o-porrino/1.0'});r.raise_for_status();return r.text
        urls=self.inventory_urls(fetch(self.SOURCE));groups={}
        for url in urls:
            time.sleep(0.35)
            year,docs=self.parse_inventory(fetch(url),url)
            group=groups.setdefault(year,{'documents':{},'sources':[]});group['sources'].append(url)
            for d in docs:group['documents'][urlparse(d['url']).path]=d
        rows=[{'id':f'o-porrino-proy-pxom-{year}','municipio':'O Porriño','titulo':f'PXOM {year}',
               'tipo':'plan_general','fecha':None,'url':g['sources'][0],'source':'ayuntamiento',
               'origen':'instrumento_planeamiento_documentado','documentos':list(g['documents'].values()),
               'source_urls':g['sources']} for year,g in sorted(groups.items())]
        return self._write(out_jsonl,rows)
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
