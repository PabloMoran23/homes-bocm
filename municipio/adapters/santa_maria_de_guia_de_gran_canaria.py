"""Municipal approved-planning table; one record per instrument, not per PDF."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://santamariadeguia.es/area-de-desarrollo-urbanismo/'
LIMITATIONS = [
    'Snapshot of the municipal Planeamiento Aprobado table, not a complete planning register.',
    'PGO attachments cover links on its landing page only; nested document sections remain linked through the index.',
    'PERI and PEPRI dates and current legal validity are not independently established; approved is the municipal inventory classification.',
    'No granted licences, procurement, news, pending planning or general ordinances extracted.',
    'No verified instrument geometry; no coordinates inferred from PDF maps or municipality location.',
    'The 2026 initial modification at Barranco de Las Garzas is outside this approved-table source.',
]


def canonical(base, href):
    parts = urlsplit(urljoin(base, href.replace('\\', '/')))
    if parts.hostname not in {'santamariadeguia.es', 'www.plangeneralguiagc.es', 'plangeneralguiagc.es'}:
        raise ValueError('Unexpected planning document host')
    return urlunsplit(('https', parts.netloc, quote(unquote(parts.path), safe='/'), parts.query, ''))


def reject_pagination(soup):
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                re.fullmatch(r'(siguiente|next|[»›])', a.get_text(' ', strip=True), re.I)):
            raise ValueError('Pagination appeared; refusing a partial inventory')
    if soup.select('.pagination, .page-numbers, .nav-links'):
        raise ValueError('Pagination markup appeared; review inventory traversal')


def record(key, title, url):
    return dict(id='35023-planeamiento-' + key, municipio='Santa María de Guía de Gran Canaria',
                codigo_ine='35023', provincia='Las Palmas', titulo=title,
                tipo='planeamiento_urbanistico', fase='aprobado (clasificación del inventario municipal)',
                fecha=None, fecha_publicacion=None, fecha_acuerdo=None, fecha_aprob=None,
                url=url, source='ayuntamiento', origen='inventario_municipal_planeamiento_aprobado',
                documentos=[], lat=None, lon=None, geometry=None,
                geometry_status='unavailable', publication_ready=False)


def add_document(row, anchor, base):
    url = canonical(base, anchor['href'])
    if urlsplit(url).path.lower().endswith('.pdf'):
        if not any(d['url'] == url for d in row['documentos']):
            row['documentos'].append({'titulo': anchor.get_text(' ', strip=True) or unquote(urlsplit(url).path.rsplit('/', 1)[-1]),
                                      'url': url, 'source_url': base})


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    reject_pagination(soup)
    tables = [t for t in soup.select('table') if 'Planeamiento Aprobado' in t.get_text(' ', strip=True)]
    if len(tables) != 1:
        raise ValueError('Approved municipal table absent or ambiguous')
    records = {}
    active = False
    current = None
    for tr in tables[0].select('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 4:
            raise ValueError('Planning table column structure changed')
        label = cells[0].get_text(' ', strip=True)
        if label:
            active = label == 'Planeamiento Aprobado'
            current = None
        if not active:
            continue
        for a in cells[1].select('a[href]'):
            if a.get_text(' ', strip=True) != 'Plan General en Vigor':
                raise ValueError('Unreviewed instrument in approved table')
            url = canonical(SOURCE, a['href'])
            if not urlsplit(url).path.startswith('/PGO2017/'):
                raise ValueError('PGO portal changed')
            records['pgo'] = record('pgo', 'Plan General de Ordenación de Santa María de Guía', url)
        name = cells[2].get_text(' ', strip=True)
        if name:
            key = {'Peri La Atalaya': 'peri-la-atalaya', 'Pepri Guía': 'pepri-guia'}.get(name)
            if key is None:
                raise ValueError('Unreviewed special plan in municipal table: ' + name)
            current = records.setdefault(key, record(key, name, SOURCE))
        anchors = cells[3].select('a[href]')
        if anchors and current is None:
            raise ValueError('Planning documents without an instrument')
        for a in anchors:
            add_document(current, a, SOURCE)
    if set(records) != {'pgo', 'peri-la-atalaya', 'pepri-guia'}:
        raise ValueError('Reviewed instruments disappeared from municipal inventory')
    if any(not r['documentos'] for k, r in records.items() if k != 'pgo'):
        raise ValueError('Special plan lacks documents')
    return list(records.values())


MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def contextual_date(text, prefix):
    match = re.search(prefix + r'\s+(\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    if not match:
        raise ValueError('PGO date narrative changed: ' + prefix)
    return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()


def enrich_pgo(row, html):
    soup = BeautifulSoup(html, 'html.parser')
    reject_pagination(soup)
    paragraphs = [' '.join(p.get_text(' ', strip=True).split()) for p in soup.select('p')]
    narrative = [p for p in paragraphs if 'fue aprobado definitivamente' in p]
    if len(narrative) != 1 or 'Santa María de Guía' not in narrative[0]:
        raise ValueError('Unverified PGO approval narrative')
    text = narrative[0]
    row.update(fase='aprobación definitiva', descripcion=text,
               fecha_acuerdo=contextual_date(text, 'sesión celebrada el'),
               fecha_aprob=contextual_date(text, 'sesión celebrada el'),
               fecha_publicacion=contextual_date(text, 'Boletín Oficial de la Provincia de'),
               fecha_entrada_vigor=contextual_date(text, 'entrada en vigor el día'),
               fecha_publicacion_tipo='publicación íntegra de normativa en BOP',
               fuentes=[SOURCE, row['url']], cobertura_documental='PDFs de portada; se conserva el índice para las secciones anidadas')
    for a in soup.select('a[href]'):
        add_document(row, a, row['url'])
    if not row['documentos']:
        raise ValueError('PGO landing page lacks documents')


class SantaMariaDeGuiaDeGranCanariaAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-35023-planning/1.0'})
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Unexpectedly large planning HTML')
        response.encoding = response.apparent_encoding
        html = response.text
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE))
        pgo = next(r for r in rows if r['id'].endswith('-pgo'))
        enrich_pgo(pgo, self._fetch(pgo['url']))
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE, pgo['url']], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
