"""Two documented instruments discovered in Hondarribia's municipal resource inventory.

A complete snapshot of these two document collections, not all municipal planning.
No PDF date inference, licence extraction or synthetic geometry.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.hondarribia.eus'
SOURCE = BASE + '/es/recursos-geograficos-urbanismo'
LIMITATIONS = [
    'Cobertura parcial: nuevo PGOU y Plan Director Muralla; no todo el planeamiento municipal.',
    'Excluye NNSS y modificaciones, PGOU formalmente no vigente, convenios, cartografía y estudio hidráulico de Mendelu.',
    'Las fechas de los rótulos documentales se conservan como texto, salvo anuncio BOG explícito; no se infieren fechas desde archivos.',
    'PDF/ZIP enlazados, sin interpretar su contenido ni verificar todos los binarios; geometría no disponible.',
    'Sin licencias concedidas; sin noticias, formularios ni anuncios de contratación.',
]


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#content')
    if main is None:
        raise ValueError('Missing municipal content container')
    for a in main.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        rel = a.get('rel', [])
        if a['href'] not in ('', '#') and (
            'next' in rel or label in {'siguiente', 'next', 'hurrengoa', '›', '»'}
            or re.search(r'(?:cur|page|start)=\d+', a['href'], re.I)
        ):
            raise ValueError('Pagination appeared; review traversal before accepting snapshot')
    return main


def official_url(base, href):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.hondarribia.eus':
        raise ValueError('Unexpected source host or scheme: ' + url)
    return url.split('#')[0]


class HondarribiaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        main = content(html)
        if 'Recursos Geográficos y de Urbanismo' not in main.get_text(' ', strip=True):
            raise ValueError('Unexpected resource inventory')
        paths = {
            '/es/hapo/contenido-aprobacion-provisional-plan': 'pgou',
            '/es/plan-director-muralla-hondarribia': 'muralla',
        }
        found = {}
        for a in main.select('a[href]'):
            path = urlparse(urljoin(SOURCE, a['href'])).path
            if path in paths:
                found[paths[path]] = official_url(SOURCE, a['href'])
        if set(found) != {'pgou', 'muralla'}:
            raise ValueError('Supported instruments missing from live municipal inventory')
        return found

    @staticmethod
    def parse_documents(html, url):
        main = content(html)
        docs = {}
        for a in main.select('a[href]'):
            if '/documents/' not in urlparse(urljoin(url, a['href'])).path:
                continue
            link = official_url(url, a['href'])
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Unlabelled document')
            block = a.find_parent(class_='relacionados_descarga')
            section = block.select_one('.titulo') if block else None
            # Keep URL query/version exactly as published; UUID identifies duplicates.
            uuid = urlparse(link).path.rstrip('/').rsplit('/', 1)[-1]
            docs.setdefault(uuid, {'titulo': title, 'url': link, 'source_url': url,
                                   'seccion': section.get_text(' ', strip=True) if section else None})
        if not docs:
            raise ValueError('Instrument has no source documents: ' + url)
        return list(docs.values())

    @classmethod
    def parse_instrument(cls, key, html, url):
        main = content(html)
        text = main.get_text(' ', strip=True)
        if key == 'pgou':
            match = re.search(r'El Pleno acordó la aprobación provisional del PGOU en la sesión del (\d{1,2}) de (\w+) de (\d{4})', text)
            months = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
            if not match or match[2] not in months:
                raise ValueError('Missing explicit PGOU provisional approval narrative')
            approved = date(int(match[3]), months.index(match[2]) + 1, int(match[1])).isoformat()
            title, kind, phase = 'Plan General de Ordenación Urbana de Hondarribia', 'PGOU', 'aprobación provisional'
        elif key == 'muralla' and 'Plan Director Muralla de Hondarribia' in text:
            title, kind, phase, approved = 'Plan Director Muralla de Hondarribia', 'plan_director', None, None
        else:
            raise ValueError('Unexpected instrument content')
        return {'id': 'hondarribia-proy-' + key, 'municipio': 'Hondarribia',
                'codigo_ine': '20036', 'provincia': 'Gipuzkoa', 'titulo': title,
                'tipo': kind, 'fase': phase, 'fecha': None, 'fecha_acuerdo': approved,
                'fecha_aprob': approved, 'fecha_publicacion': None, 'url': url,
                'source': 'ayuntamiento', 'origen': 'inventario_recursos_urbanismo',
                'source_inventory_url': SOURCE, 'documentos': cls.parse_documents(html, url),
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-hondarribia/1.0'

            def fetch(url):
                official_url(BASE, url)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                official_url(BASE, response.url)
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Expected HTML inventory, got another content type')
                source_urls.append(url)
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    name = urlparse(url).path.strip('/').replace('/', '_') + '.html'
                    (folder / name).write_bytes(response.content)
                return response.text

            inventory = self.parse_inventory(fetch(SOURCE))
            rows = []
            for key, url in inventory.items():
                html = fetch(url)
                row = self.parse_instrument(key, html, url)
                if key == 'pgou':
                    main = content(html)
                    links = {official_url(url, a['href']) for a in main.select('a[href]')
                             if a.get_text(' ', strip=True) == 'Información pública y documentación'}
                    if len(links) != 1:
                        raise ValueError('PGOU procedural document inventory missing or ambiguous')
                    procedure_url = links.pop()
                    docs = self.parse_documents(fetch(procedure_url), procedure_url)
                    announcements = [d for d in docs if 'Anuncio en el BOG de la aprobación provisional del PGOU' in d['titulo']]
                    if len(announcements) != 1:
                        raise ValueError('Missing explicit provisional approval publication')
                    label = announcements[0]['titulo']
                    row['fecha_publicacion'] = datetime.strptime(label[:10], '%d-%m-%Y').date().isoformat()
                    row['fecha_publicacion_source_url'] = procedure_url
                    row['fecha_acuerdo_source_url'] = url
                    row['documentos'].extend(d for d in docs if d['url'] not in {x['url'] for x in row['documentos']})
                rows.append(row)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'document_counts': {r['id']: len(r['documentos']) for r in rows},
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
