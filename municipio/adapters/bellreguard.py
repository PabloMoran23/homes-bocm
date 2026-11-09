"""Partial documentary inventory of Bellreguard's Plan General, not licences."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://web.bellreguard.net/urbanisme/'


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


class BellreguardAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        headings = [h for h in soup.select('h1') if _norm(h.get_text(' ', strip=True)) ==
                    'ordenacio urbanistica. planols i normativa']
        if len(headings) != 1:
            raise ValueError('Missing or ambiguous municipal planning inventory heading')
        column = headings[0].find_parent('div', class_='et_pb_column')
        inventories = column.select('.et_pb_accordion') if column else []
        if len(inventories) != 1:
            raise ValueError('Planning document inventory changed')
        inventory = inventories[0]
        if column.select('[rel~=next], .pagination, .et_pb_posts_nav, .nav-links'):
            raise ValueError('Paginated planning inventory requires crawler review')
        roles = {
            'nomativa urbanistica': 'normativa',  # spelling on the official page
            'normativa urbanistica': 'normativa',
            'zona urbanistica poble': 'plano_pueblo',
            'zona urbanistica mar': 'plano_playa',
        }
        docs = {}
        seen_roles = set()
        for item in inventory.select('.et_pb_accordion_item'):
            heading = item.select_one('.et_pb_toggle_title')
            role = roles.get(_norm(heading.get_text(' ', strip=True))) if heading else None
            if not role or role in seen_roles:
                raise ValueError('Unreviewed or duplicate instrument/document group')
            seen_roles.add(role)
            links = item.select('a[href]')
            if not links:
                raise ValueError('Planning group lacks documents')
            for link in links:
                url = urljoin(SOURCE, link['href'])
                parsed = urlparse(url)
                if (parsed.scheme != 'https' or parsed.netloc != 'web.bellreguard.net'
                        or not parsed.path.startswith('/wp-content/uploads/')
                        or not parsed.path.lower().endswith('.pdf')):
                    raise ValueError('Unreviewed planning document URL')
                title = link.get_text(' ', strip=True)
                if not title:
                    raise ValueError('Document lacks source title')
                docs.setdefault(url, {'titulo': title, 'url': url, 'rol': role, 'source_url': SOURCE})
        if seen_roles != {'normativa', 'plano_pueblo', 'plano_playa'}:
            raise ValueError('Incomplete planning document inventory')
        return [{
            'id': 'bellreguard-plan-general', 'municipio': 'Bellreguard',
            'codigo_ine': '46048', 'provincia': 'Valencia',
            'titulo': 'Plan General de Bellreguard — normativa y planos',
            'tipo': 'planeamiento_urbanistico', 'url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
            'documentos': list(docs.values()),
            'descripcion': 'Documentación del Plan General publicada en el bloque municipal de normativa y planos. Cobertura documental parcial; no acredita vigencia ni aprobación.',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }]

    def _fetch(self, url: str, *, pdf=False) -> bytes:
        # Read to completion within a bound; never accept a truncated response.
        with requests.get(url, timeout=45, stream=True,
                          headers={'User-Agent': 'municipio-bellreguard/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 20_000_000:
                    raise ValueError('Source exceeds reviewed response size')
                chunks.append(chunk)
            content = b''.join(chunks)
            if pdf and ('application/pdf' not in response.headers.get('Content-Type', '').lower()
                        or not content.startswith(b'%PDF-')):
                raise ValueError('Planning document is not a PDF')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = Path(urlparse(url).path).name if pdf else 'urbanisme.html'
            (directory / name).write_bytes(content)
        return content

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = self.parse_projects(self._fetch(SOURCE).decode('utf-8'))
        for row in rows:
            for document in row['documentos']:
                self._fetch(document['url'], pdf=True)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of this bounded documentary block, no date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
