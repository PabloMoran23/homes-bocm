"""Current partial-plan inventory from Roses' official Plone planning portal."""
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

class RosesAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE='https://www.roses.cat/la-vila/urbanisme/planejament/planejament-vigent/plans-parcials-pgou'
    @classmethod
    def parse_inventory(cls,html):
        soup=BeautifulSoup(html,'html.parser');core=soup.select_one('#content-core')
        if core is None:raise ValueError('Missing Plone inventory content')
        rows=[]
        for tile in core.select('.tileItem'):
            a=tile.select_one('.tileHeadline a[href]');d=tile.select_one('.description')
            if not a:continue
            title=a.get_text(' ',strip=True);url=urljoin(cls.SOURCE,a['href'])
            if not re.search(r'PLA PARCIAL',title,re.I) or not url.startswith(cls.SOURCE+'/'):continue
            desc=d.get_text(' ',strip=True) if d else ''
            row={'id':'roses-proy-'+hashlib.sha256(url.encode()).hexdigest()[:14],'municipio':'Roses',
                 'titulo':title,'tipo':'plan_parcial','fecha':None,'url':url,'source':'ayuntamiento',
                 'origen':'instrumento_planeamiento_vigente','descripcion':desc or None,'descripcion_source_url':cls.SOURCE}
            match=re.search(r'Aprovaci[oó] definitiva\s+\w+\s+(\d{2}\.\d{2}\.\d{4})',desc,re.I)
            if match:
                row['fecha_aprobacion']=datetime.strptime(match.group(1),'%d.%m.%Y').date().isoformat()
                row['fase']='aprobacion_definitiva'
            rows.append(row)
        next_link=soup.select_one('.listingNext a[href], a[rel="next"]')
        return rows,urljoin(cls.SOURCE,next_link['href']) if next_link else None
    @staticmethod
    def _write(path,rows):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');temp.replace(path)
        return {'rows':len(rows),'status':'ok'}
    def backfill_proyectos(self,out_jsonl):
        def fetch(url):
            r=requests.get(url,timeout=25,headers={'User-Agent':'poc-bocm-roses/1.0'});r.raise_for_status();return r.text
        url=self.SOURCE;seen=set();rows={}
        while url:
            if url in seen or len(seen)>=20:raise ValueError('Pagination loop/limit; refusing partial inventory')
            if not url.startswith(self.SOURCE):raise ValueError('Unexpected pagination URL')
            seen.add(url);page,url=self.parse_inventory(fetch(url));rows.update((r['id'],r) for r in page)
            time.sleep(.35)
        if not rows:raise ValueError('No named partial plans found')
        for row in rows.values():
            core=BeautifulSoup(fetch(row['url']),'html.parser').select_one('#content-core')
            if core is None:raise ValueError('Missing plan detail')
            docs={}
            for a in core.select('a[href]'):
                link=urljoin(row['url'],a['href'])
                if urlparse(link).hostname=='www.roses.cat' and re.search(r'\.pdf(?:\?|$)|/@@download/',link,re.I):
                    docs.setdefault(link,{'titulo':a.get_text(' ',strip=True),'url':link})
            if not docs:raise ValueError('Named plan lacks source documents')
            row['documentos']=list(docs.values());time.sleep(.35)
        return self._write(out_jsonl,list(rows.values()))
    def update_proyectos(self,out_jsonl,state_path):return self.backfill_proyectos(out_jsonl)
    def backfill_licencias(self,out_jsonl):return self._write(out_jsonl,[])
    def update_licencias(self,out_jsonl,state_path):return self.backfill_licencias(out_jsonl)
