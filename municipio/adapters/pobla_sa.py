"""Sa Pobla's municipal NNSS document inventory (a partial planning snapshot)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://sapobla.cat/ca/serveis-municipals/urbanisme'


class PoblaSaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main')
        if not main or not main.select_one('h1') or main.select_one('h1').get_text(strip=True) != 'Urbanisme':
            raise ValueError('Missing municipal Urbanisme inventory')
        if main.select('.pager, .pagination, a[rel~=next]'):
            raise ValueError('Pagination detected; inventory traversal requires review')
        for a in main.select('a[href]'):
            if a.get_text(' ', strip=True).casefold() in {'següent', 'siguiente', 'next', 'següent ›', '›', '»'}:
                raise ValueError('Pagination detected; refusing a truncated snapshot')
        plans, bulletins = {}, {}
        for heading in main.select('h3'):
            title = heading.get_text(' ', strip=True)
            is_plan = re.fullmatch(r'Normes subsidiàries de sa Pobla (\d{4})', title)
            is_boib = title == 'BOIB acord de les NNSS de sa Pobla'
            if not (is_plan or is_boib):
                continue
            card = heading.parent
            while card is not None and card is not main and not card.select('a[href]'):
                card = card.parent
            if card is None or card is main:
                raise ValueError('Planning document card has no link')
            anchors = card.select('a[href]')
            if len(anchors) != 1:
                raise ValueError('Ambiguous document card')
            url = urljoin(SOURCE, anchors[0]['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https':
                raise ValueError('Unverified document scheme')
            if is_plan:
                if parsed.hostname != 'drive.google.com' or not re.fullmatch(r'/file/d/[\w-]+/view', parsed.path):
                    raise ValueError('Unreviewed plan document host or path')
                url = 'https://drive.google.com' + parsed.path
            elif parsed.hostname != 'sapobla.cat' or not parsed.path.startswith('/sites/cilma_sa_pobla/files/') or not parsed.path.lower().endswith('.pdf'):
                raise ValueError('Unreviewed municipal BOIB document URL')
            doc = {'titulo': title, 'url': url, 'url_procedencia': SOURCE,
                   'rol': 'documento_planeamiento' if is_plan else 'publicacion_boib_relacionada'}
            # This is the portal's file date, NOT a planning agreement date.
            file_date = re.search(r'\b\d{2}/\d{2}/\d{4}\b', card.get_text(' ', strip=True))
            if file_date:
                doc['fecha_archivo_portal'] = file_date[0]
            (plans if is_plan else bulletins)[url] = doc
        if len(plans) != 1 or not bulletins:
            raise ValueError('Expected one NNSS instrument and its related BOIB documents')
        plan_url, plan = next(iter(plans.items()))
        return [{
            'id': 'pobla-sa-proy-' + hashlib.sha256(plan_url.encode()).hexdigest()[:16],
            'municipio': 'Pobla, Sa', 'codigo_ine': '07044', 'provincia': 'Illes Balears',
            'titulo': plan['titulo'], 'tipo': 'planeamiento_urbanistico',
            'url': SOURCE, 'url_documento': plan_url,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanisme',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None,
            'documentos': [plan, *bulletins.values()],
            'descripcion': 'Instrumento NNSS enlazado por el área municipal de Urbanisme. '
                           'El BOIB relacionado contiene la modificación puntual 1 y texto refundido; '
                           'no acredita la fecha de aprobación del plan base de 2003.',
            'cobertura': 'Parcial: documentos NNSS enlazados en Urbanisme; no inventario histórico completo.',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }]

    def _fetch(self, url: str, capture: str) -> requests.Response:
        response = requests.get(url, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-pobla-sa/1.0')})
        response.raise_for_status()
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = self._fetch(SOURCE, 'urbanisme.html')
        response.encoding = 'utf-8'
        rows = self.parse_inventory(response.text)
        for i, doc in enumerate(rows[0]['documentos']):
            is_plan = doc['rol'] == 'documento_planeamiento'
            response = self._fetch(doc['url'], f'document-{i}.html' if is_plan else f'document-{i}.pdf')
            if is_plan:
                title = BeautifulSoup(response.text, 'html.parser').title
                if not title or not re.search(r'NNSS.*2003.*\.pdf', title.get_text(), re.I):
                    raise ValueError('Linked NNSS document is unavailable or has changed identity')
            elif not response.content.startswith(b'%PDF-'):
                raise ValueError('BOIB link did not return a PDF')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, *[d['url'] for d in rows[0]['documentos']]],
                'coverage': 'partial', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'Application forms are not granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
