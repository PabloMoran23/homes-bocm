"""Es Mercadal: complete snapshots of two municipal planning document inventories."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.aj-esmercadal.org'
SOURCES = (BASE + '/ca/NORMES_SUBSIDIaRIES_ES_MERCADAL/20358',
           BASE + '/ca/AVAN_PLA_PGOU_MERCADAL/12605')
LIMITATIONS = [
    'Partial municipal coverage: only the NS and PGOU inventories linked by Urbanisme; no licence register or exhaustive works history.',
    'Inventory headings and document labels are provenance, not independent verification of current legal validity.',
    'No approval/agreement/publication dates extracted; document month/year is retained only in document titles.',
    'No verified coordinates or geometry; publication_ready is false.',
    'Map-series landing pages and the legacy maps link are retained, not recursively harvested; PDF contents are not parsed.',
]


def _record(key, title, kind, source):
    return dict(id='mercadal-es-plan-' + key, municipio='Mercadal, Es',
                codigo_ine='07037', provincia='Illes Balears', titulo=title,
                tipo=kind, fase=None, fecha=None, fecha_publicacion=None,
                fecha_acuerdo=None, fecha_aprob=None, url=source,
                inventory_url=source, source='ayuntamiento',
                origen='inventario_planeamiento', documentos=[],
                lat=None, lon=None, geometry=None, publication_ready=False,
                geometry_status='unavailable')


def parse_inventory(html: str, source: str) -> list[dict]:
    if source not in SOURCES:
        raise ValueError('Unknown Es Mercadal inventory')
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.PLA_texte')
    heading = soup.select_one('.PLA_titol')
    expected = 'NORMES SUBSIDIÀRIES VIGENTS' if source == SOURCES[0] else 'AVANÇ PLA PGOU MERCADAL'
    if not content or not heading or heading.get_text(' ', strip=True).upper() != expected:
        raise ValueError('Municipal inventory markup/title changed')
    # These are static document pages, not a news search. Fail if paging appears.
    if content.select('[class*="pagin"], [id*="pagin"], a[rel="next"]'):
        raise ValueError('Unexpected pagination; extraction must not truncate')
    records = {}
    for a in content.select('a[href]'):
        label = ' '.join(a.get_text(' ', strip=True).split())
        target = urljoin(source, a['href'])
        parts = urlsplit(target)
        if parts.scheme != 'https' or parts.hostname != 'www.aj-esmercadal.org':
            raise ValueError('Unexpected document origin')
        # requests accepts encoded URLs; preserve existing escapes and encode spaces/Unicode.
        target = quote(target, safe=":/?=&%+;#@")
        if source == SOURCES[1]:
            if not parts.path.lower().endswith('.pdf') or '/PGOU/' not in parts.path:
                raise ValueError('Unexpected PGOU inventory link')
            key, title, kind = 'pgou-avanc', expected, 'avance de PGOU'
        else:
            match = re.match(r'^Mod\.\s*Punt\s*(\d+)\b', label, re.I)
            if match:
                key = 'ns-mod-' + match[1]
                title = 'Modificació puntual ' + match[1] + ' de les Normes Subsidiàries des Mercadal'
                kind = 'modificación de normas subsidiarias'
            elif label.lower().startswith('estudi detall '):
                key = 'estudi-' + re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
                title, kind = label, 'estudio de detalle'
            elif (label.startswith(('Revisió NS', 'Plànols de norme', 'Sèrie '))
                  or 'Quadre resum' in label or '/Patrimoni/' in parts.path):
                key, title, kind = 'ns-1994', 'Normes Subsidiàries des Mercadal — Revisió NS 1994', 'normas subsidiarias'
            else:
                raise ValueError('Unclassified inventory link: ' + label)
        row = records.setdefault(key, _record(key, title, kind, source))
        doc = dict(titulo=label, url=target, source_url=source,
                   tipo='pdf' if parts.path.lower().endswith('.pdf') else 'pagina_documental')
        if doc not in row['documentos']:
            row['documentos'].append(doc)
    if not records:
        raise ValueError('Empty municipal planning inventory')
    for row in records.values():
        pdfs = [d for d in row['documentos'] if d['tipo'] == 'pdf']
        if not pdfs:
            raise ValueError('Instrument without a document')
        # Prefer the revision over the summary table for the NS principal document.
        principal = next((d for d in pdfs if d['titulo'].startswith('Revisió NS')), pdfs[0])
        row['url_documento'] = principal['url']
        row['descripcion'] = 'Inventario municipal: ' + expected + '. Documentos: ' + '; '.join(d['titulo'] for d in row['documentos'])
    return list(records.values())


class MercadalEsAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='mercadal-es', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        capture_dir = self.config.get('capture_dir')
        for source in SOURCES:
            response = requests.get(source, timeout=40, headers={
                'User-Agent': 'municipio-mercadal-es/1.0 (public planning inventory)'})
            response.raise_for_status()
            if response.url != source:
                raise ValueError('Unexpected inventory redirect: ' + response.url)
            response.encoding = 'utf-8'
            rows.extend(parse_inventory(response.text, source))
            if capture_dir:
                folder = Path(capture_dir)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / ('inventory-' + source.rsplit('/', 1)[1] + '.html')).write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return dict(status='ok', rows=len(rows), source_urls=list(SOURCES),
                    coverage='complete snapshots of two static inventories; partial municipality coverage',
                    limitations=LIMITATIONS, publication_ready=False)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return dict(status='disabled', rows=0, reason='No verified public register of granted licences')

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
