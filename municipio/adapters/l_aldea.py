"""Snapshot of the municipal planning-document inventory hosted on seu-e.cat."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/aldea/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')


class LAldeaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://laldea.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        inventories = [block for block in soup.select('.journal-content-article')
                       if 'Text refós de les Normes Subsidiàries' in block.get_text(' ', strip=True)]
        if len(inventories) != 1:
            raise ValueError('Missing or ambiguous municipal planning inventory')
        block = inventories[0]
        if block.select('a[rel~=next], .pagination, .pager') or any(
            re.search(r'[?&]page=|/page/\d+', a['href'])
            or a.get_text(' ', strip=True).lower() in {'següent', 'siguiente', 'next', '»'}
            for a in block.select('a[href]')
        ):
            raise ValueError('Inventory pagination detected; crawler must be extended')
        docs = {}
        for a in block.select('a[href]'):
            title = a.get_text(' ', strip=True)
            url = urljoin(SOURCE, a['href'])
            parts = urlsplit(url)
            if '/documents/' not in parts.path:
                continue  # MUC viewer is a general service, not an instrument.
            if parts.hostname not in {'www.seu-e.cat', 'seu-e.cat'} or not parts.path.startswith('/documents/28831/'):
                raise ValueError('Unexpected document provenance')
            url = urlunsplit(('https', 'seu-e.cat', parts.path, '', ''))
            if title.startswith('Text refós de les Normes Subsidiàries') and "L'Aldea" in title:
                role = 'normativa'
            elif title == "Mapa de Planejament de L'Aldea.":
                role = 'plano'
            elif title == 'Estudi de Mobilitat Urbana Sostenible':
                role = 'estudio_movilidad'
            else:
                raise ValueError('Unreviewed planning document: ' + title)
            if role in docs and docs[role]['url'] != url:
                raise ValueError('Conflicting documents for ' + role)
            docs[role] = {'titulo': title, 'url': url, 'rol': role, 'url_fuente': SOURCE}
        if not {'normativa', 'plano'} <= docs.keys():
            raise ValueError('Planning inventory lacks the norms or associated map')
        groups = [('normativa', 'normas_subsidiarias', [docs['normativa'], docs['plano']])]
        if 'estudio_movilidad' in docs:
            groups.append(('estudio_movilidad', 'estudio_movilidad', [docs['estudio_movilidad']]))
        rows = []
        for key, kind, documents in groups:
            primary = docs[key]
            rows.append({
                'id': 'l-aldea-proy-' + hashlib.sha256(primary['url'].encode()).hexdigest()[:16],
                'municipio': "L'Aldea", 'codigo_ine': '43904', 'provincia': 'Tarragona',
                'titulo': primary['titulo'], 'tipo': kind,
                'fase': None, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'url_documento': primary['url'], 'documentos': documents,
                'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
                'descripcion': ('Instrumento y documentos publicados en el inventario municipal. '
                                'La página no indica fechas de acuerdo ni de publicación del instrumento.'),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'Sin geometría vectorial verificada; no se geocodifica el mapa PDF.',
            })
        return rows

    def _fetch(self, url: str, limit: int) -> bytes:
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipio-l-aldea/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source response exceeds reviewed size limit')
                chunks.append(chunk)
            return b''.join(chunks)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        html = self._fetch(SOURCE, 3_000_000)
        rows = self.parse_projects(html.decode('utf-8'))
        capture = self.config.get('evidence_dir')
        if capture:
            capture = Path(capture)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(html)
        # Validate every attachment, including the associated map. A failed
        # download aborts the snapshot before replacing the previous output.
        source_urls = [SOURCE]
        for row in rows:
            for doc in row['documentos']:
                data = self._fetch(doc['url'], 80_000_000)
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Expected PDF source document: ' + doc['url'])
                source_urls.append(doc['url'])
                doc['sha256'] = hashlib.sha256(data).hexdigest()
                if capture:
                    (capture / (doc['rol'] + '.pdf')).write_bytes(data)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'coverage': 'Partial municipal planning-document inventory snapshot',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
