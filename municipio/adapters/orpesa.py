"""Public municipal planning archive, delegated by the town website to Drive."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.oropesadelmar.es/es/descargas/urbanismo-y-medio-ambiente'
ROOT = '0B5fl2C1HLL08a3FSSTd2b2dkT1U'
RESTORATION_FOLDER = '1k9bgdNFlB7RP8JK8UfcwNAhhGlzUuRyW'
LIMITATIONS = [
    'Partial coverage: public Urbanismo download archive only; not a complete municipal dossier register.',
    'File names identify instruments; PDF/archive contents are not parsed for approvals or current legal validity.',
    'Drive last-modified labels are retained verbatim and are not publication or agreement dates.',
    'No verified granted licences or project geometry; no inferred coordinates.',
]


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def classify(title, folder):
    text = norm(title).replace('_', ' ')
    if folder == RESTORATION_FOLDER or 'proyecto de restauracion' in text:
        return 'restauracion-r2c-r14', 'Proyecto de restauración de parcelas R2C y R14, Torre Bellver', 'proyecto_restauracion'
    if 'catalaneta' in text:
        return 'urbanizacion-ue2-catalaneta', 'Proyecto de urbanización UE 2 La Catalaneta', 'proyecto_urbanizacion'
    if 'palmavera' in text:
        return 'mp-palmavera', 'Modificación del PGOU Palmavera', 'modificacion_planeamiento'
    if 'r4b y r5a' in text:
        return 'mp-1-2015', 'Modificación puntual PGOU 1-2015, PP R4B y R5A', 'modificacion_planeamiento'
    if '2-2016' in text and 'noroeste' in text:
        return 'mp-2-2016', 'Modificación puntual PGOU 2-2016, sector noroeste', 'modificacion_planeamiento'
    patterns = [
        ('la colomera', 'pe-colomera', 'Plan especial La Colomera', 'plan_especial'),
        ('torrepaquita', 'pai-torrepaquita', 'PAI mediante gestión directa, calle Torrepaquita', 'pai'),
        ('memoria ambiental y sintesis pgou', 'pgou-memoria-2017', 'PGOU: memoria ambiental y síntesis 2017', 'planeamiento_general'),
        ('1.2023 residencia', 'mp-1-2023', 'Modificación puntual 1.2023, residencia y centro de día Els Cuarts', 'modificacion_planeamiento'),
        ('1 2017 centro salud', 'mp-1-2017', 'Modificación puntual 1/2017 Centro de Salud', 'modificacion_planeamiento'),
        ('22015 - apertura vial', 'mp-2-2015', 'Modificación puntual 2/2015, apertura vial José Rivera Forner', 'modificacion_planeamiento'),
        ('pgou 1-2014', 'mp-1-2014', 'Modificación puntual PGOU 1-2014', 'modificacion_planeamiento'),
        ('plan parcial torre bellver', 'mp-torre-bellver-2', 'Modificación del texto refundido del plan parcial Torre Bellver, segunda fase', 'modificacion_planeamiento'),
        ('paseo maritimo mediterraneo', 'legalizacion-paseo-mediterraneo', 'Proyecto de legalización de la urbanización del Paseo Marítimo Mediterráneo entre avenida del Mar y calle Galicia', 'proyecto_urbanizacion'),
        ('expropiacion deposito agua', 'expropiacion-deposito', 'Proyecto de expropiación depósito de agua', 'proyecto_expropiacion'),
        ('vial servicio y aceras parcelas r3', 'urbanizacion-r3-cht2', 'Proyecto de urbanización vial de servicio y aceras, parcelas R3 y CHT2', 'proyecto_urbanizacion'),
        ('m.p.1 21 els quarts', 'mp-1-2021', 'Modificación puntual 1/21 Els Quarts Este: conclusión de fase ambiental', 'modificacion_planeamiento'),
    ]
    for pattern, key, name, kind in patterns:
        if pattern in text:
            return key, name, kind
    # Legal rules, application forms and an isolated water-supply agreement are
    # explicitly excluded, rather than treated as physical works or licences.
    if any(word in text for word in ('solicitud', 'ordenanza', 'convenio desaladora')):
        return None
    raise ValueError(f'Unreviewed archive document: {title}')


def parse_folder(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select_one('.flip-entries'):
        raise ValueError('Public folder entries missing (login, error or changed markup)')
    if soup.select('[rel=next], .pager, .pagination, [data-next-page-token]') or re.search(r'nextPageToken|load.more|siguiente|next page', soup.get_text(' ', strip=True), re.I):
        raise ValueError('Folder pagination detected; refusing incomplete snapshot')
    result = []
    for entry in soup.select('.flip-entry'):
        a, title = entry.select_one('a[href]'), entry.select_one('.flip-entry-title')
        if not a or not title:
            raise ValueError('Incomplete Drive entry')
        url = a['href']
        parsed = urlparse(url)
        match = re.fullmatch(r'/(file/d|drive/folders)/([\w-]+)(?:/view)?', parsed.path)
        if parsed.scheme != 'https' or parsed.hostname != 'drive.google.com' or not match:
            raise ValueError('Unexpected public archive link')
        modified = entry.select_one('.flip-entry-last-modified')
        result.append({'id': match[2], 'folder': match[1] == 'drive/folders',
                       'titulo': title.get_text(' ', strip=True), 'url': url,
                       'fecha_modificacion_archivo_texto': modified.get_text(' ', strip=True) if modified else None})
    # The reviewed embedded view is a static, server-rendered listing. Fail on
    # growth to a typical page boundary rather than assume it is still complete.
    if len(result) >= 50:
        raise ValueError('Folder reached unverified listing size; review pagination')
    return result


class OrpesaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='orpesa', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.oropesadelmar.es')
        self.source_urls = []

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-orpesa/1.0'})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError('Archive HTML exceeds reviewed size')
        self.source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        soup = BeautifulSoup(self._fetch(SOURCE), 'html.parser')
        frames = soup.select('article iframe[src]')
        urls = [f['src'] for f in frames if urlparse(f['src']).hostname == 'drive.google.com'
                and urlparse(f['src']).path == '/embeddedfolderview'
                and parse_qs(urlparse(f['src']).query).get('id') == [ROOT]]
        if len(urls) != 1:
            raise ValueError('Municipal provenance link to reviewed archive missing')
        queue = [(ROOT, urls[0])]
        visited, records, excluded = set(), {}, []
        while queue:
            folder, url = queue.pop(0)
            if folder in visited:
                continue
            visited.add(folder)
            if len(visited) > 20:
                raise ValueError('Folder traversal exceeded reviewed scope')
            for item in parse_folder(self._fetch(url)):
                if item['folder']:
                    queue.append((item['id'], 'https://drive.google.com/embeddedfolderview?id=' + item['id']))
                    continue
                classification = classify(item['titulo'], folder)
                if not classification:
                    excluded.append(item)
                    continue
                key, title, kind = classification
                row = records.setdefault(key, {
                    'id': 'orpesa-proy-' + key, 'municipio': 'Orpesa / Oropesa del Mar',
                    'codigo_ine': '12085', 'provincia': 'Castellón', 'titulo': title,
                    'tipo': kind, 'fase': None, 'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None, 'url': SOURCE,
                    'source': 'ayuntamiento', 'origen': 'archivo_municipal_urbanismo',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'descripcion': 'Instrumento identificado en el archivo público municipal; vigencia y aprobación no verificadas.',
                })
                existing = next((d for d in row['documentos'] if d['id'] == item['id']), None)
                if existing:
                    if url not in existing['inventarios']:
                        existing['inventarios'].append(url)
                else:
                    row['documentos'].append({**item, 'inventarios': [url]})
        if not records:
            raise ValueError('No usable municipal instruments found')
        rows = sorted(records.values(), key=lambda r: r['id'])
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'excluded_documents': excluded,
                'folders_visited': len(visited)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
