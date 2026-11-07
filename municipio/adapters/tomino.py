"""Official planning inventory; documents are grouped by instrument."""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://tomino.gal/area-de-urbanismo/'


class TominoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        if (soup.select('a[rel~=next], .pagination, .page-numbers, .wp-pagenavi')
                or any(a.get_text(' ', strip=True).lower() in {'siguiente', 'seguinte', 'next'}
                       and a.get('href') not in {None, '', '#'} for a in soup.select('a[href]'))):
            raise ValueError('Pagination detected; review before extracting partial inventory')
        rows = {}
        active = ended = False
        for heading in soup.select('h3, h5.title-holder'):
            title = heading.get_text(' ', strip=True)
            if heading.name == 'h3':
                if title == 'Plan Xeral de Ordenación Municipal (PXOM) e outros planeamentos':
                    active = True
                    continue
                if active:
                    if title != 'Trámites e Procedementos':
                        raise ValueError(f'Unexpected inventory boundary: {title}')
                    ended = True
                    break
                continue
            if not active or title.startswith('INSTRUCCIÓN DE SERVIZO'):
                continue
            match = re.match(r'^M\.P\. Nº (\d+[AB]?)\s*-', title)
            if title.startswith('PXOM 2001'):
                key, name, kind = 'pxom-2001', 'Plan Xeral de Ordenación Municipal de Tomiño (PXOM 2001)', 'planeamiento_urbanistico'
            elif match:
                key, name, kind = 'mp-' + match[1].lower(), title, 'modificacion_planeamiento'
            elif title == 'PEPID Altos de Torona':
                key, name, kind = 'pepid-altos-de-torona', title, 'planeamiento_urbanistico'
            elif title == 'URBANIZACIÓN DA A.R. 4 (GOIÁN)':
                key, name, kind = 'urbanizacion-ar4-goian', title, 'proyecto_urbanizacion'
            else:
                raise ValueError(f'Unreviewed planning heading: {title}')
            block = heading.find_next_sibling()
            if block is None or 'accordion_content' not in block.get('class', []):
                raise ValueError(f'Missing document block: {title}')
            docs = {}
            for link in block.select('a[href]'):
                raw = link['href'].strip()
                # Repair only the observed municipal triple-slash typo; retain raw href.
                repaired = re.sub(r'^http:///tomino\.gal/', 'https://tomino.gal/', raw)
                url = urljoin(SOURCE, repaired)
                parts = urlsplit(url)
                municipal = (parts.hostname in {'tomino.gal', 'www.tomino.gal'}
                             and '/wp-content/uploads/' in parts.path
                             and parts.path.lower().endswith(('.pdf', '.zip')))
                drive = parts.hostname == 'drive.google.com' and parts.path.startswith('/file/d/')
                if parts.scheme not in {'http', 'https'} or not (municipal or drive):
                    raise ValueError(f'Unreviewed document URL: {raw}')
                docs.setdefault(url, {'titulo': link.get_text(' ', strip=True), 'url': url,
                                      'href_original': raw, 'seccion': title, 'url_procedencia': SOURCE})
            if not docs:
                raise ValueError(f'No documents: {title}')
            if key not in rows:
                rows[key] = {
                    'id': 'tomino-proy-' + key, 'municipio': 'Tomiño',
                    'codigo_ine': '36054', 'provincia': 'Pontevedra',
                    'titulo': name, 'tipo': kind,
                    'fase': 'aprobación inicial' if '(APROBACIÓN INICIAL)' in title else None,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                    'documentos': [], 'secciones': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'geometry_status': 'Sin geometría verificada; planos enlazados sin georreferenciar',
                }
            row = rows[key]
            row['secciones'].append(title)
            existing = {d['url'] for d in row['documentos']}
            row['documentos'].extend(d for u, d in docs.items() if u not in existing)
        if not active or not ended or not rows or 'pxom-2001' not in rows:
            raise ValueError('Missing or incomplete municipal planning inventory')
        return list(rows.values())

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE]}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=45, headers={'User-Agent': 'municipio-tomino/1.0'}, stream=True) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname not in {'tomino.gal', 'www.tomino.gal'}:
                raise ValueError('Unexpected source redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 5_000_000:
                    raise ValueError('Inventory exceeds 5 MB; review source')
        rows = self.parse_projects(content.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html.gz').write_bytes(gzip.compress(bytes(content), mtime=0))
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of the single-page inventory; not a historical event log.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
