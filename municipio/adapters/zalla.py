"""Zalla PGOU document inventory: one instrument, multiple supporting documents."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://zallaplanorokorra.eus/es/'


class ZallaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        if not any(h.get_text(' ', strip=True) == 'Nuevo PGOU de Zalla' for h in soup.select('h2')):
            raise ValueError('Missing Zalla PGOU identity')
        # This is a single plan microsite, not a municipality-wide project register.
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'hurrengoa'} or
                '/page/' in a['href']):
                raise ValueError('Pagination discovered; review before accepting a partial inventory')
        headings = [h for h in soup.select('h2') if h.get_text(' ', strip=True) == 'Documentos']
        if len(headings) != 1:
            raise ValueError('Missing or ambiguous document inventory')
        section = headings[0].parent
        while section and not section.select('a[href]'):
            section = section.parent
        if section is None or section.name in {'body', 'html', '[document]'}:
            raise ValueError('Document inventory structure changed')
        docs = {}
        for a in section.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            title = a.get_text(' ', strip=True)
            # Questionnaire solicits input; it is not a planning document.
            if parsed.hostname == 'forms.gle':
                continue
            is_pdf = (parsed.hostname in {'zallaplanorokorra.eus', 'www.zallaplanorokorra.eus'}
                      and parsed.path.startswith('/wp-content/uploads/')
                      and parsed.path.lower().endswith('.pdf'))
            is_folder = parsed.hostname == 'www.dropbox.com' and parsed.path.startswith('/scl/fo/')
            if not title or not (is_pdf or is_folder) or parsed.scheme != 'https':
                raise ValueError(f'Unrecognized document link: {url}')
            docs.setdefault(url, {'titulo': title, 'url': url, 'source_url': SOURCE,
                                  'formato': 'PDF' if is_pdf else 'carpeta de planos',
                                  'procedencia': 'enlace publicado en la web municipal del PGOU'})
        titles = {d['titulo'] for d in docs.values()}
        required = {'AVANCE: MEMORIA', 'AVANCE: PLANOS', 'AVANCE: DOCUMENTO INICIAL ESTRATÉGICO'}
        if not required <= titles:
            raise ValueError('Incomplete core PGOU documentation')
        return [{
            'id': 'zalla-proy-pgou', 'municipio': 'Zalla', 'codigo_ine': '48096',
            'provincia': 'Bizkaia', 'titulo': 'Nuevo PGOU de Zalla',
            'tipo': 'plan_general_ordenacion_urbana', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pgou',
            'descripcion': 'Documentación del nuevo Plan General: avance, documento inicial '
                           'estratégico, planos y participación. La web describe fases previstas; '
                           'no permite determinar por sí sola la fase administrativa actual.',
            'documentos': list(docs.values()), 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': 'Solo el nuevo PGOU; no inventario completo del planeamiento ni de obras. '
                         'Carpeta externa de planos enlazada, sin enumerar su contenido. '
                         'Sin fechas explícitas del inventario; no se derivan de rutas de archivos.',
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=35, headers={'User-Agent': 'municipio-zalla/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'zallaplanorokorra.eus', 'www.zallaplanorokorra.eus'}:
            raise ValueError('Unexpected source redirect')
        rows = self.parse_projects(response.text)
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'live-pgou.html').write_bytes(response.content)
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete snapshot of the single-instrument inventory on each refresh.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
