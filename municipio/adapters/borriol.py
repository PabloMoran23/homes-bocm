"""Municipal l'Abeller project dossier; deliberately partial urbanism coverage."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.borriol.es/es/proyectos-de-urbanizacion/'
SEDE_HOST = 'borriol.sedelectronica.es'
LIMITATIONS = [
    "Cobertura parcial: expediente de urbanización l'Abeller enlazado por la web municipal; no inventario completo de obras o planeamiento.",
    'Sin licencias concedidas, coordenadas ni estado de ejecución verificados.',
    'No se deducen fechas de publicación, aprobación o acuerdo del año del certificado ni de la fecha de creación del documento.',
    'Los enlaces documentales son fichas públicas de la sede; no se interpreta el contenido de los PDF.',
]


def reject_pagination(soup):
    """Fail closed if the reviewed single-page dossier gains navigation."""
    for node in soup.select('a, button, input, [class]'):
        classes = ' '.join(node.get('class', []))
        if (re.search(r'pag(?:inat|er)|navigator', classes, re.I)
                or 'next' in node.get('rel', [])
                or (node.name in {'a', 'button', 'input'}
                    and any(re.fullmatch(r'(?:siguiente|next|següent|última)(?: página| page)?[ »›]*', value.strip(), re.I)
                            for value in (node.get_text(' ', strip=True), node.get('title', ''),
                                          node.get('aria-label', ''), node.get('value', ''))))
                or re.search(r'/page/\d|[?&](?:page|pagina)=', node.get('href', ''))):
            raise ValueError('Pagination detected; extend crawler before extracting')


def discover_dossier(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None or not re.search(r'abeller', main.get_text(' ', strip=True), re.I):
        raise ValueError("Municipal page no longer identifies l'Abeller")
    reject_pagination(main)
    links = {urljoin(url, a['href']) for a in main.select('a[href]')
             if urlparse(urljoin(url, a['href'])).hostname == SEDE_HOST
             and re.fullmatch(r'/transparency/[0-9a-f-]{36}/?', urlparse(urljoin(url, a['href'])).path)}
    if len(links) != 1:
        raise ValueError('Expected one project dossier; review expanded/changed municipal inventory')
    return links.pop()


def parse_dossier(html, url, inventory_url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#content')
    table = soup.select_one('table.TransparencyListPanel')
    if main is None or table is None:
        raise ValueError('Missing public dossier table')
    reject_pagination(main)
    # Folder breadcrumb immediately precedes the table container; no generated title.
    breadcrumb = table.parent.find_previous_sibling('span')
    if breadcrumb is None:
        raise ValueError('Missing dossier breadcrumb')
    title = re.sub(r'^\d+[.\-\s]+', '', breadcrumb.get_text(' ', strip=True).split('/')[-1]).strip()
    if not re.search(r"PROGRAMA DE ACTUACI[ÓO]N INTEGRADA L['’]ABELLER", title, re.I):
        raise ValueError('Unexpected dossier identity')
    documents = {}
    for cell in table.select('td.class_name'):
        anchors = cell.select('a.gIconLink')
        if not anchors:
            if cell.get_text(strip=True):
                raise ValueError('Unparsed dossier entry')
            continue
        for a in anchors:
            target = urljoin(url, a.get('href', ''))
            if (urlparse(target).hostname != SEDE_HOST
                    or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path)
                    or 'exp' in a.get('class', [])):
                raise ValueError('Unsupported document/folder; refusing partial dossier')
            label = a.get_text(' ', strip=True)
            if not label:
                raise ValueError('Document lacks title')
            documents[target] = {'titulo': label, 'descripcion_fuente': a.get('title', ''),
                                 'url': target, 'source_url': url}
    if not documents or not any(re.search(r'\bmemoria\b', d['titulo'], re.I) for d in documents.values()):
        raise ValueError('No substantive project memory in dossier')
    return [{
        'id': 'borriol-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Borriol', 'provincia': 'Castellón', 'codigo_ine': '12031',
        'titulo': title, 'tipo': 'proyecto_urbanizacion', 'url': url,
        'inventory_url': inventory_url, 'source': 'ayuntamiento',
        'origen': 'expediente_documental_urbanismo',
        'documentos': list(documents.values()), 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'expediente_abeller_parcial',
    }]


class BorriolAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipal-inventory/1.0 (public urban planning)'

            def fetch(url, filename):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname != urlparse(url).hostname:
                    raise ValueError('Unexpected source redirect')
                if 'html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected HTML inventory')
                source_urls.append(response.url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / filename).write_bytes(response.content)
                return response.text

            dossier = discover_dossier(fetch(SOURCE, 'municipal-projects.html'))
            rows = parse_dossier(fetch(dossier, 'abeller-dossier.html'), dossier)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh of this small current dossier, not an inferred incremental history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
