"""El Catllar's municipal planning inventory (partial, not a licence register)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/elcatllar/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/planejament-urbanistic')
HEADERS = ['Data aprovació', 'Data publicació', 'Rang', 'Instrument',
           'Número expedient', 'Competència', 'Tema', 'Publicacions a diaris oficials',
           'Enllaç', 'Documents', 'Més informació']
RPUC = re.compile(r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/(\d+)(?:/documents)?/?$')


def _date(value):
    return datetime.strptime(value, '%d-%m-%Y').date().isoformat() if value else None


class ElCatllarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.elcatllar.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        if 'Ajuntament del Catllar' not in title or 'Planejament urbanístic' not in title:
            raise ValueError('Unexpected municipal planning page or login/error response')
        tables = [t for t in soup.find_all('table') if
                  [h.get_text(' ', strip=True) for h in t.select('thead th')] == HEADERS]
        if len(tables) != 1:
            raise ValueError('Planning inventory schema missing or ambiguous')
        table = tables[0]
        # This source embeds ALL rows; DataTables only paginates them in the browser.
        # Fail if it changes to remote data or server-side pagination.
        for script in soup.find_all('script'):
            text = script.get_text()
            if table.get('id', '__missing__') in text and re.search(
                    r'[\"\']?(?:serverSide|bServerSide|ajax|sAjaxSource)[\"\']?\s*:', text):
                raise ValueError('Remote/paginated inventory requires crawler review')
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if ('next' in a.get('rel', []) or label in {'següent', 'siguiente', 'next'}):
                if a['href'] not in {'', '#'}:
                    raise ValueError('Unfollowed pagination in inventory')
        records = {}
        for tr in table.select('tbody tr'):
            # The live HTML omits closing </tr> tags. Direct cells prevent nested
            # rows from leaking their dates/documents into the first record.
            cells = tr.find_all('td', recursive=False)
            values = [c.get_text(' ', strip=True) for c in cells]
            if not any(values) and not any(c.select('a[href]') for c in cells):
                continue
            if len(cells) != len(HEADERS):
                raise ValueError('Incomplete planning inventory row')
            if not values[6]:
                raise ValueError('Nonempty inventory row has no instrument title')
            if not re.match(r"(?:Pla\b|Modificació puntual del Pla\b)", values[6], re.I):
                raise ValueError('Unreviewed instrument type in planning table')
            documents = {}
            dossiers = set()
            for cell in cells:
                for a in cell.select('a[href]'):
                    url = urljoin(SOURCE, a['href'])
                    if not url.startswith(('https://', 'http://')):
                        raise ValueError('Unsupported document URL')
                    match = RPUC.fullmatch(url)
                    if match:
                        dossiers.add(match[1])
                    documents.setdefault(url, {'titulo': a.get_text(' ', strip=True),
                                                'url': url, 'source_url': SOURCE,
                                                'tipo': 'expediente_rpuc' if match else 'enlace_fuente'})
            if len(dossiers) != 1:
                raise ValueError('Planning row lacks one unambiguous RPUC dossier')
            dossier = next(iter(dossiers))
            row = {
                'id': 'el-catllar-proy-rpuc-' + dossier,
                'municipio': 'El Catllar', 'provincia': 'Tarragona', 'codigo_ine': '43043',
                'titulo': values[6], 'tipo': 'planeamiento_urbanistico', 'fase': None,
                'fecha': None, 'fecha_aprob': _date(values[0]),
                'fecha_publicacion': _date(values[1]), 'fecha_acuerdo': None,
                'expediente': values[4] or None, 'rpuc_id': dossier,
                'rango_fuente': values[2] or None, 'instrumento_fuente': values[3] or None,
                'competencia_fuente': values[5] or None,
                'publicaciones_oficiales_fuente': values[7] or None,
                'mas_informacion_fuente': values[10] or None,
                'url': SOURCE, 'url_documento': next(u for u in documents if RPUC.fullmatch(u)),
                'documentos': list(documents.values()), 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planejament',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Partial municipal planning inventory; not all RPUC instruments',
            }
            if dossier in records:
                old = records[dossier]
                # Group duplicate document rows without losing conflicting metadata.
                if any(old[k] != row[k] for k in row if k not in {'documentos', 'url_documento'}):
                    raise ValueError('Conflicting metadata for one RPUC instrument')
                by_url = {d['url']: d for d in old['documentos']}
                by_url.update(documents)
                old['documentos'] = list(by_url.values())
            else:
                records[dossier] = row
        if not records:
            raise ValueError('No usable planning instruments in official inventory')
        return list(records.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=(10, 40), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-el-catllar/1.0')}) as response:
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML planning inventory')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Planning page exceeds reviewed size; no partial output')
                chunks.append(chunk)
            payload = b''.join(chunks)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planejament.html').write_bytes(payload)
        rows = self.parse_projects(payload.decode('utf-8'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'publication_ready': False, 'coverage': 'partial'}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the complete embedded inventory, without date-based filtering."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
