"""Current municipal POM document inventory; no inferred licences or dates."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://elvisodesanjuan.org/areas-municipales/urbanismo-servicios/'
HOST = 'elvisodesanjuan.org'


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    if urlparse(url).hostname != HOST or urlparse(url).path != urlparse(SOURCE).path:
        raise ValueError('Unexpected inventory URL')
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#wpb-content-root')
    if content is None:
        raise ValueError('Municipal content container missing')
    # This inventory is a single page. Refuse a newly paginated version rather
    # than silently extracting only its first page.
    if (soup.select_one('a[rel~=next], link[rel~=next]') or
            content.select_one('.pagination, .page-numbers, .wp-pagenavi') or
            any(re.search(r'(?:[?&](?:page|paged)=|/page/\d+)', a['href'])
                for a in content.select('a[href]'))):
        raise ValueError('Pagination detected: inventory traversal needs review')
    docs = {}
    plan_titles = set()
    for a in content.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        label = a.get_text(' ', strip=True)
        if not parsed.path.lower().endswith('.pdf'):
            continue
        if parsed.hostname != HOST or parsed.scheme != 'https' or not parsed.path.startswith('/pdf/'):
            raise ValueError('Unexpected document provenance: ' + target)
        match = re.fullmatch(r'(Plan de Ordenación Municipal El Viso de San Juan):\s*(.+)', label, re.I)
        if match:
            plan_titles.add(match[1])
            suffix = match[2].upper()
            if suffix == 'NORMAS URBANÍSTICAS':
                role = 'normas_urbanisticas'
            elif suffix == 'FICHAS RESUMEN DE ÁMBITOS URBANÍSTICOS':
                role = 'fichas_ambitos'
            else:
                raise ValueError('Unrecognised POM document: ' + label)
        elif re.fullmatch(r'Plano \d+', label, re.I):
            role = 'plano_clasificacion_calificacion'
        elif re.fullmatch(r'Ordenación Estructural Plano \d+', label, re.I):
            role = 'plano_ordenacion_estructural'
        elif label.upper() in {'RED DE AGUA', 'RED DE SANEAMIENTO', 'RED DE ENERGÍA ELÉCTRICA', 'ESQUEMA DE TRÁFICO'}:
            role = 'plano_infraestructuras'
        else:
            raise ValueError('Unrecognised inventory PDF: ' + label)
        document = {'titulo': label, 'url': target, 'tipo': role, 'source_url': url}
        if target in docs and docs[target] != document:
            raise ValueError('Conflicting labels for document: ' + target)
        docs[target] = document
    roles = {d['tipo'] for d in docs.values()}
    if len(plan_titles) != 1 or not {'normas_urbanisticas', 'fichas_ambitos'} <= roles:
        raise ValueError('Named POM and its principal documents not found')
    return [{
        'id': 'el-viso-de-san-juan-pom',
        'municipio': 'El Viso de San Juan', 'codigo_ine': '45199', 'provincia': 'Toledo',
        'titulo': next(iter(plan_titles)), 'tipo': 'Plan de Ordenación Municipal',
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'url': url, 'inventory_url': url,
        'url_documento': next(d['url'] for d in docs.values() if d['tipo'] == 'normas_urbanisticas'),
        'documentos': list(docs.values()),
        'descripcion': 'Instrumento agrupado con normas urbanísticas, fichas de ámbitos y planos enlazados en el inventario municipal.',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fase': None, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'Inventario documental actual del POM; no acredita vigencia ni cobertura completa del planeamiento o de obras.',
    }]


class ElVisoDeSanJuanAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.Session() as session:
            session.trust_env = bool(self.config.get('trust_env', True))
            response = session.get(SOURCE, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Inventory is not HTML')
            rows = parse_inventory(response.text, response.url)
        # Optional local audit capture; no network publication or persistence of state.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'current_pom_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        """Refresh the complete current inventory; not a historical change feed."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
