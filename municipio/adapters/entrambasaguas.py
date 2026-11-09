"""Municipal planning document inventory; one instrument with its attachments."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://entrambasaguas.org/normativa-urbanistica'
PLAN = 'NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL'
LIMITATIONS = [
    'Cobertura parcial: únicamente el inventario municipal de Normativa Urbanística; '
    'no es un histórico completo de proyectos, modificaciones ni obras.',
    'La presencia en el inventario no acredita vigencia consolidada ni fase de aprobación.',
    'Sin fechas de publicación o acuerdo explícitas, ni geometría verificada. '
    'El directorio 2022-02 de los adjuntos no se interpreta como fecha del instrumento.',
    'No se extraen licencias concedidas, actas, contratación ni noticias.',
]


def official_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname in
            {'entrambasaguas.org', 'www.entrambasaguas.org'} and
            not parsed.username and not parsed.password and parsed.port in (None, 443))


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.node--type-page .node__content')
    if content is None:
        raise ValueError('Municipal planning content missing')
    # The reviewed source is a complete, unpaginated document list. Fail closed
    # on pagination rather than emit an incomplete snapshot after a site change.
    if content.select('.pager, [rel~=next], .views-infinite-scroll-content-wrapper, '
                      '[data-drupal-views-infinite-scroll-pager]') or any(
        'page=' in a['href'] or a.get_text(' ', strip=True).casefold() in
        {'siguiente', 'next', 'mostrar más', 'cargar más'}
        for a in content.select('a[href]')
    ):
        raise ValueError('Planning inventory has pagination; crawler must be extended')
    documents = {}
    for item in content.select('li.view-list-item'):
        title = item.select_one('.views-field-title')
        links = item.select('.views-field-field-archivo-normativa a[href]')
        if title is None or not links:
            raise ValueError('Planning inventory item missing title or attachment')
        label = title.get_text(' ', strip=True)
        if not label.startswith(PLAN + ' – '):
            raise ValueError('Unreviewed planning instrument; grouping must be extended')
        for a in links:
            url = urljoin(SOURCE, a['href'])
            path = unquote(urlsplit(url).path)
            if (not official_url(url) or not path.startswith('/sites/default/files/')
                    or not path.lower().endswith(('.pdf', '.zip'))
                    or 'NORMAS-SUBSIDIARIAS-DE-PLANEAMIENTO-MUNICIPAL-' not in path):
                raise ValueError('Unexpected planning attachment URL')
            documents.setdefault(url, {
                'titulo': label, 'url': url, 'source_url': SOURCE,
                'formato': path.rsplit('.', 1)[-1].lower(),
            })
    if not documents:
        raise ValueError('No municipal planning documents found')
    return [{
        'id': 'entrambasaguas-plan-normas-subsidiarias',
        'municipio': 'Entrambasaguas', 'codigo_ine': '39028', 'provincia': 'Cantabria',
        'titulo': PLAN, 'tipo': 'normas_subsidiarias',
        'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
        'url': SOURCE, 'inventory_url': SOURCE,
        'documentos': list(documents.values()),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fase': None, 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'coverage': 'inventario_documental_parcial', 'limitations': LIMITATIONS,
    }]


class EntrambasaguasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                       encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-entrambasaguas/1.0'})
        response.raise_for_status()
        if not official_url(response.url) or urlsplit(response.url).path != '/normativa-urbanistica':
            raise ValueError('Unexpected planning inventory redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Planning inventory is not HTML')
        rows = parse_inventory(response.text)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'normativa-urbanistica.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of the current inventory, not an inferred event feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
