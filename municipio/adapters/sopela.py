"""Municipal PGOU revision document inventory; no licence or news extraction."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


class SopelaAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = 'https://sopelaplanorokorra.eus/es/'

    @classmethod
    def parse_projects(cls, html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.content_inner')
        if content is None:
            raise ValueError('PGOU content missing')
        text = content.get_text(' ', strip=True)
        if not all(s in text for s in ('REVISIÓN DEL PGOU', 'Sopela', 'Documentos y formularios')):
            raise ValueError('Unrecognized Sopela PGOU inventory')
        # A single instrument landing page, not a paginated news feed. Fail if
        # its structure gains pagination rather than silently accepting page 1.
        if soup.select('[rel~=next], .pagination, .page-numbers, .wp-pagenavi'):
            raise ValueError('Pagination requires explicit review')
        for a in soup.select('a[href]'):
            if a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'hurrengoa'} and a['href'] not in {'', '#'}:
                raise ValueError('Pagination requires explicit review')
        docs = {}
        for a in content.select('a.qbutton[href]'):
            title = a.get_text(' ', strip=True)
            url = urljoin(cls.SOURCE, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https':
                continue
            municipal_file = (parsed.hostname in {'sopelaplanorokorra.eus', 'www.sopelaplanorokorra.eus'}
                              and parsed.path.startswith('/wp-content/uploads/')
                              and parsed.path.lower().endswith(('.pdf', '.jpg', '.png', '.zip')))
            plan_folder = (parsed.hostname == 'www.dropbox.com' and parsed.path.startswith('/scl/fo/')
                           and title == 'AVANCE + DOCUMENTO INICIAL ESTRATÉGICO')
            if not (municipal_file or plan_folder):
                continue
            if not title:
                raise ValueError('Source document lacks a title')
            docs.setdefault(url, {'titulo': title, 'url': url, 'source_url': cls.SOURCE,
                                  'tipo_enlace': 'carpeta_externa' if plan_folder else 'documento'})
        titles = {d['titulo'] for d in docs.values()}
        # Real plan documents are required: a timeline, form or menu alone does
        # not establish an extractable instrument. Future additions are retained.
        if not {'INFORME PREVIO', 'SÍNTESIS DEL DOCUMENTO DE INFORMACIÓN Y DIAGNÓSTICO',
                'CRITERIOS Y OBJETIVOS', 'AVANCE + DOCUMENTO INICIAL ESTRATÉGICO'} <= titles:
            raise ValueError('PGOU document inventory incomplete or changed')
        return [{
            'id': 'sopela-proy-revision-pgou', 'municipio': 'Sopela',
            'codigo_ine': '48085', 'provincia': 'Bizkaia',
            'titulo': 'Revisión del Plan General de Ordenación Urbana de Sopela',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': cls.SOURCE, 'source': 'ayuntamiento', 'origen': 'portal_revision_pgou',
            'documentos': list(docs.values()),
            'descripcion': 'Revisión del PGOU. El portal reúne documentos de información y diagnóstico, '
                           'avance, participación, síntesis de sugerencias y criterios y objetivos. '
                           'El calendario describe también fases futuras; no acredita aprobación definitiva.',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(self.SOURCE, timeout=30, headers={'User-Agent': 'municipio-sopela/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'sopelaplanorokorra.eus', 'www.sopelaplanorokorra.eus'}:
            raise ValueError('Unexpected PGOU source redirect')
        html = response.content.decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'pgou-live.html').write_text(html, encoding='utf-8')
        return {**self._write(out_jsonl, rows), 'source_urls': [self.SOURCE]}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
