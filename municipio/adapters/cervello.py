"""Cervelló's paginated municipal public-works inventory, as a full snapshot."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.cervello.cat/ajuntament/organitzacio-administrativa/obra-publica'
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()
LIMITATIONS = [
    'Partial municipal coverage: physical projects in the municipal Obra pública inventory only; not the RPUC planning register.',
    'Civil-protection, fire-prevention and air-quality policy plans excluded; no granted-licence register extracted.',
    'Document links retained, PDFs not parsed; attachment availability and geometry not verified.',
    'Website update timestamps are not publication dates; unknown dates remain null. Conditional definitive approval is never inferred.',
    'Full inventory snapshot, not a historic deletion/change log. No coordinates or municipal centroid substituted.',
]


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def phase(title):
    t = norm(title)
    if 'definitiv' in t or 'difinitiv' in t:
        return 'aprobación definitiva'
    if 'inicial' in t:
        return 'aprobación inicial'
    return 'aprobación' if t.startswith('aprovacio') else None


def instrument_key(title):
    # Ignore approval wrappers, typography and whitespace, but preserve every
    # substantive word (including phase numbers and years of the actual work).
    title = re.sub(r'^Aprovació\s+(?:(?:definitiva|difinitiva|inicial)\s+)?(?:del|de la|de l[’\'])\s*', '', title, flags=re.I)
    title = re.sub(r'\s*,?\s*aprovat definitivament.*$', '', title, flags=re.I)
    title = re.sub(r'^(Projecte) anomenat\s+', r'\1 ', title, flags=re.I)
    return re.sub(r'[^a-z0-9]+', ' ', norm(title)).strip()


def session_agreement(text):
    # Restrict to an actual council session, never the author's date, BOP
    # publication date, cited law date or a conditional future approval.
    m = re.search(r"sessió\s+(?:ordinària|extraordinària)\s+(?:de\s+)?data\s+(\d{1,2})\s+(?:de\s+|d[’'])?(\w+)\s+de\s+(\d{4})(.{0,100})", text, re.I)
    if not m or m[2].lower() not in MONTHS:
        return None
    try:
        value = date(int(m[3]), MONTHS.index(m[2].lower()) + 1, int(m[1])).isoformat()
    except ValueError:
        return None
    tail = norm(m[4])
    stage = ('aprobación inicial' if re.search(r'aprov(?:ar|at)\s+inicialment', tail)
             else 'aprobación definitiva' if re.search(r'aprov(?:ar|at)\s+definitivament', tail) else None)
    return {'fecha_acuerdo': value, 'fase': stage, 'texto_fuente': m[0]}


class CervelloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='cervello', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cervello.cat')

    @staticmethod
    def parse_inventory(html, url=SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#readspeakerPage')
        if not main or not main.select_one('h1') or main.h1.get_text(strip=True) != 'Obra pública':
            raise ValueError('Unrecognized Cervelló public-works inventory')
        links = []
        for a in main.select('li.article-item a[href]'):
            target = urljoin(url, a['href'])
            if not target.startswith(SOURCE + '/') or not target.endswith('.html'):
                raise ValueError('Unexpected inventory detail URL')
            links.append(target)
        if not links:
            raise ValueError('Empty inventory; refusing a partial snapshot')
        pages = {SOURCE}
        for a in main.select('.paginacio a[href]'):
            target = urljoin(url, a['href'])
            p = urlparse(target)
            q = parse_qs(p.query)
            if p.netloc != urlparse(SOURCE).netloc or p.path.rstrip('/') != urlparse(SOURCE).path or (p.query and (set(q) != {'pag'} or len(q['pag']) != 1 or not q['pag'][0].isdigit())):
                raise ValueError('Unexpected pagination URL')
            pages.add(target)
        for info in main.select('.paginacio .info'):
            count = re.search(r'(\d+)\s+pàgines', info.get_text())
            if count and len(pages) != int(count[1]):
                raise ValueError('Pagination count disagrees with exposed page links')
        return list(dict.fromkeys(links)), sorted(pages)

    @staticmethod
    def parse_detail(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#readspeakerPage')
        if not main or not main.select_one('h1'):
            raise ValueError('Missing project detail')
        title = main.h1.get_text(' ', strip=True)
        # Deliberately narrow: only identified works, never policy plans/forms.
        if not re.match(r'^(?:Aprovació.*(?:projecte|memòria valorada)|Projecte)', title, re.I):
            return None
        if not phase(title) and not title.startswith('Projecte'):
            raise ValueError('Unrecognized approval heading')
        body = main.select_one('.ddbbtext')
        text = body.get_text(' ', strip=True) if body else ''
        docs = {}
        for a in soup.select('#page-documents a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).scheme not in {'http', 'https'}:
                raise ValueError('Invalid document URL')
            docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': url})
        if not text and not docs:
            raise ValueError('Project has neither narrative nor source documents')
        event = session_agreement(text)
        return {'titulo': title, 'url': url, 'fase': phase(title),
                'descripcion': text, 'fecha_publicacion': None,
                'fecha_acuerdo': event['fecha_acuerdo'] if event and event['fase'] == phase(title) else None,
                'acuerdos': [event] if event else [], 'documentos': list(docs.values())}

    @staticmethod
    def group_projects(notices):
        grouped = {}
        for notice in notices:
            key = instrument_key(notice['titulo'])
            grouped.setdefault(key, []).append(notice)
        rows = []
        for key, group in sorted(grouped.items()):
            # Definitive over initial, preserving every notice and its evidence.
            best = max(group, key=lambda n: {'aprobación definitiva': 2, 'aprobación inicial': 1}.get(n['fase'], 0))
            docs = {}
            for n in group:
                for d in n['documentos']:
                    docs.setdefault((d['url'], d['source_url']), d)
            rows.append({
                'id': 'cervello-proy-' + hashlib.sha256(key.encode()).hexdigest()[:20],
                'municipio': 'Cervelló', 'codigo_ine': '08068', 'provincia': 'Barcelona',
                'titulo': best['titulo'], 'tipo': 'proyecto_obra_publica', 'fase': best['fase'],
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': best['fecha_acuerdo'],
                'url': best['url'], 'source': 'ayuntamiento', 'origen': 'inventario_obra_publica',
                'descripcion': best['descripcion'], 'anuncios': group,
                'documentos': list(docs.values()), 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False,
            })
        if not rows:
            raise ValueError('No usable physical public works extracted')
        return rows

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 45), stream=True,
                          headers={'User-Agent': 'municipio-cervello/1.0'}) as r:
            r.raise_for_status()
            data = bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data) > 5_000_000:
                    raise ValueError('Oversized HTML; refusing truncation')
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_bytes(data)
            return data.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, details = [SOURCE], set(), set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety bound reached; output not written')
            links, pages = self.parse_inventory(self._fetch(url), url)
            visited.add(url)
            details.update(links)
            pending.extend(p for p in pages if p not in visited and p not in pending)
        notices, excluded = [], []
        for url in sorted(details):
            notice = self.parse_detail(self._fetch(url), url)
            if notice is None:
                excluded.append(url)
            else:
                notices.append(notice)
        rows = self.group_projects(notices)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': sorted(visited),
                'source_urls': sorted(visited | details), 'detail_pages': len(details),
                'included_notices': len(notices), 'excluded_urls': excluded,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
