"""Complete snapshots of two municipal planning inventories; no licence feed."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.llicamunt.cat'
PLANNING = BASE + '/seu-electronica/urbanisme/planejament-urbanistic-'
STUDIES = BASE + '/seu-electronica/urbanisme/estudis-de-detall'


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def checked_page(html, title):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    heading = main.find('h1') if main else None
    if not heading or text(heading) != title:
        raise ValueError('Missing municipal inventory heading: ' + title)
    if soup.select('[rel~=next], .pagination, .paginacio, .paginador'):
        raise ValueError('Inventory pagination detected; crawler must be extended')
    for a in main.select('a[href]'):
        if text(a).casefold() in {'següent', 'següents', 'siguiente', 'next', '›', '»'}:
            raise ValueError('Inventory continuation detected; refusing truncation')
    return main


def document(a, source, section, description=None):
    url = urljoin(source, a['href'])
    host = urlparse(url).hostname
    if host not in {'www.llicamunt.cat', 'llicamunt.cat', 'dogc.gencat.cat'}:
        raise ValueError('Unexpected planning document host: ' + url)
    if not urlparse(url).path.lower().endswith('.pdf') and host != 'dogc.gencat.cat':
        raise ValueError('Unexpected planning attachment: ' + url)
    return {'titulo': text(a), 'url': url, 'url_fuente': source,
            'seccion': section, 'descripcion': description}


def record(key, title, source, kind, phase=None):
    return {
        'id': 'llica-d-amunt-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': "Lliçà d'Amunt", 'provincia': 'Barcelona', 'codigo_ine': '08107',
        'titulo': title, 'tipo': kind, 'fase': phase,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'url': source, 'source': 'ayuntamiento',
        'origen': 'inventario_planeamiento_municipal', 'documentos': [],
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
    }


class LlicaDAmuntAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_planning(html):
        main = checked_page(html, 'Planejament urbanístic')
        content = main.select_one('.ddbbtext')
        if not content or 'planejament urbanístic vigent' not in text(content):
            raise ValueError('Missing current planning narrative')
        poum = "Pla d'ordenació urbanística municipal (POUM)"
        grouped_sections = {'Normes urbanístiques', 'Plànols',
            "Correcció d'errades materials al Pla d'ordenació urbanística municipal de Lliçà d'Amunt"}
        modifications = "Modificacions del Pla d'ordenació urbanística municipal"
        approved = "Planejament aprovat definitivament per l'Ajuntament"
        other = 'Altre planejament no publicat al Registre'
        excluded = 'Suspensió de llicències'
        rows = {'poum': record(PLANNING + '#poum', poum, PLANNING, 'POUM', 'vigente')}
        section = None
        seen = set()
        for block in content.find_all(['h2', 'h3', 'ul'], recursive=False):
            if block.name in {'h2', 'h3'}:
                section = text(block)
                if section not in grouped_sections | {poum, modifications, approved, other, excluded, 'Planejament urbanístic'}:
                    raise ValueError('Unreviewed inventory section: ' + section)
                seen.add(section)
                continue
            if section == excluded:
                continue  # A suspension is neither an instrument nor a granted licence.
            if section not in grouped_sections | {modifications, approved, other}:
                raise ValueError('Unclassified inventory list')
            for li in block.find_all('li', recursive=False):
                anchors = li.select('a[href]')
                if not anchors:
                    raise ValueError('Instrument without source document')
                description = text(li)
                if section not in grouped_sections and not re.match(
                        r'^(?:Modificació |Aprovació definitiva Modificació |Pla |Anunci BOPB\s+Pla |PMU-\d)', description):
                    raise ValueError('Unrecognized instrument title: ' + description)
                docs = [document(a, PLANNING, section, description) for a in anchors]
                if section in grouped_sections:
                    key = 'poum'
                else:
                    # Announcement and full plan are explicitly the same PMU-6.
                    key = 'pmu-6' if re.search(r'\bPMU-6\b', description) else docs[0]['url']
                    if key not in rows:
                        title = description
                        title = re.sub(r'\s*VEURE DOGC$', '', title).strip()
                        if key == 'pmu-6':
                            title = 'Pla de Millora Urbana PMU-6 Pinsos Tenes'
                        phase = 'aprobación definitiva' if section == approved or 'Aprovació definitiva' in title else None
                        kind = 'modificacion_planeamiento' if section == modifications or title.startswith('Modificació') else 'planeamiento_urbanistico'
                        rows[key] = record(key, title, PLANNING, kind, phase)
                existing = {d['url'] for d in rows[key]['documentos']}
                rows[key]['documentos'].extend(d for d in docs if d['url'] not in existing)
        if not {poum, modifications, approved, other}.issubset(seen):
            raise ValueError('Incomplete planning inventory structure')
        if any(not row['documentos'] for row in rows.values()):
            raise ValueError('Planning instrument lacks documents')
        return list(rows.values())

    @staticmethod
    def parse_studies(html):
        main = checked_page(html, 'Estudis de detall')
        if "estudis de detall vigents" not in text(main):
            raise ValueError('Missing current detail-study narrative')
        tables = main.find_all('table')
        if len(tables) != 1:
            raise ValueError('Expected one complete detail-study table')
        table = tables[0]
        headers = [text(th) for th in table.select('th')]
        expected = ['Expedient', 'Emplaçament', 'Qualificació urbanística', 'Clau',
                    'Documentació escrita', 'Documentació gràfica', 'Documentació administrativa']
        if headers != expected:
            raise ValueError('Detail-study table schema changed')
        rows, seen = [], set()
        for tr in table.select('tr'):
            cells = tr.find_all('td', recursive=False)
            if not cells:
                continue
            if len(cells) != 7:
                raise ValueError('Incomplete detail-study row')
            dossier, address, zoning, code = [text(c) for c in cells[:4]]
            if not re.fullmatch(r'ED \d+-\d{2}', dossier) or dossier in seen:
                raise ValueError('Invalid or duplicate detail-study dossier: ' + dossier)
            seen.add(dossier)
            row = record(STUDIES + '#' + dossier, f'Estudi de detall {dossier} — {address}',
                         STUDIES, 'estudio_detalle', 'vigente')
            row.update(expediente=dossier, direccion=address, calificacion_urbanistica=zoning, clave=code)
            for header, cell in zip(headers[4:], cells[4:]):
                anchors = cell.select('a[href]')
                if not anchors:
                    raise ValueError('Detail-study document missing: ' + dossier)
                row['documentos'].extend(document(a, STUDIES, header) for a in anchors)
            rows.append(row)
        if not rows:
            raise ValueError('Empty detail-study inventory')
        return rows

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-llica-d-amunt/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.llicamunt.cat':
                raise ValueError('Unexpected inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds response bound; refusing truncation')
                chunks.append(chunk)
            data = b''.join(chunks)
            if self.config.get('capture_dir'):
                target = Path(self.config['capture_dir'])
                target.mkdir(parents=True, exist_ok=True)
                (target / capture_name).write_bytes(data)
            return data.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_planning(self._fetch(PLANNING, 'planejament.html'))
        rows += self.parse_studies(self._fetch(STUDIES, 'estudis.html'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [PLANNING, STUDIES],
                'coverage': 'Two municipal inventories only; not the complete RPUC register',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full replacement: deletions and changed attachments are reflected.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
