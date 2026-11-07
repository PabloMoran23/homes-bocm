"""Municipal physical-works spreadsheets linked by Cehegín's transparency portal."""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://transparencia.cehegin.es/p/182-modificacion-de-las-obras-mas-importantes'
HOST = 'transparencia.cehegin.es'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def norm(value):
    return ' '.join(unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().upper().split())


def inventory_links(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find(['h1', 'h2'], string=re.compile('Modificación de las obras', re.I))
    if not heading:
        raise ValueError('Expected municipal works inventory heading missing')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or norm(a.get_text(' ', strip=True)) in {'SIGUIENTE', 'NEXT', '»'}
                or a.find_parent(class_=re.compile('pagination'))):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected: review inventory before extracting')
    links = {}
    for a in soup.select('table a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if parsed.path.lower().endswith('.xlsx'):
            if parsed.hostname != HOST or parsed.scheme != 'https' or not parsed.path.startswith('/storage/uploads/'):
                raise ValueError('Unexpected document origin')
            target = quote(unquote(target), safe=':/?=&')
            links[target] = a.get_text(' ', strip=True)
    if not links:
        raise ValueError('No municipal works spreadsheets')
    return links


def excel_date(value, date1904):
    if not value:
        return None
    number = float(value)
    if number != int(number) or number < 1:
        raise ValueError('Unexpected Excel date')
    epoch = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    return (epoch + timedelta(days=number)).date().isoformat()


def parse_workbook(content, document_url):
    """Read every workbook sheet; match explicit work-inventory column headers."""
    records = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        props = workbook.find('m:workbookPr', NS)
        date1904 = props is not None and props.get('date1904') in {'1', 'true'}
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si', NS):
                strings.append(''.join(t.text or '' for t in item.findall('.//m:t', NS)))
        rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        for sheet in workbook.findall('m:sheets/m:sheet', NS):
            target = rels[sheet.get(REL)]
            path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            root = ET.fromstring(archive.read(path))
            headers = None
            sheet_records = 0
            for row in root.findall('m:sheetData/m:row', NS):
                cells = {}
                for cell in row.findall('m:c', NS):
                    column = re.sub(r'\d+', '', cell.get('r', ''))
                    v = cell.find('m:v', NS)
                    value = v.text or '' if v is not None else ''
                    if cell.get('t') == 's':
                        value = strings[int(value)]
                    elif cell.get('t') == 'inlineStr':
                        value = ''.join(t.text or '' for t in cell.findall('.//m:t', NS))
                    cells[column] = value.strip()
                if not any(cells.values()):
                    continue
                title_header = norm(cells.get('A', ''))
                if title_header in {'NOMBRE DE LA OBRA', 'DENOMINACION DE LA OBRA'}:
                    headers = {col: norm(val) for col, val in cells.items()}
                    if headers.get('B') not in {'FECHA INICIO', 'FECHA DE INICIO'} or headers.get('C') not in {'FECHA FIN', 'PLAZO DE EJECUCION'}:
                        raise ValueError('Unknown work-inventory schema')
                    continue
                if headers is None:
                    if title_header == 'PROYECTOS DE OBRAS':
                        continue
                    raise ValueError('Unrecognized nonempty worksheet')
                title = cells.get('A', '')
                if not title:
                    raise ValueError('Work row has data without a name')
                row_data = {'titulo': title, 'documentos': [{
                    'url': document_url, 'titulo': unquote(urlparse(document_url).path.rsplit('/', 1)[-1]),
                    'hoja': sheet.get('name'), 'fila': int(row.get('r')),
                    'campos_originales': {headers.get(c, c): v for c, v in cells.items()},
                }]}
                if cells.get('B'):
                    row_data['fecha_inicio'] = excel_date(cells['B'], date1904)
                if headers['C'] == 'FECHA FIN' and cells.get('C'):
                    row_data['fecha_fin'] = excel_date(cells['C'], date1904)
                elif cells.get('C'):
                    row_data['plazo_ejecucion'] = cells['C']
                records.append(row_data)
                sheet_records += 1
            if headers is not None and not sheet_records:
                raise ValueError('Empty works worksheet')
    if not records:
        raise ValueError('Workbook contains no works')
    return records


def group_works(rows):
    grouped = {}
    for row in rows:
        key = norm(row['titulo'])
        if key not in grouped:
            grouped[key] = {
                'id': 'cehegin-obra-' + hashlib.sha256(key.encode()).hexdigest()[:20],
                'municipio': 'Cehegín', 'codigo_ine': '30017', 'provincia': 'Murcia',
                'tipo': 'obra_publica', 'source': 'ayuntamiento', 'origen': 'inventario_obras_transparencia',
                'url': SOURCE, 'inventory_url': SOURCE, 'publication_ready': False,
                'geometry_status': 'unavailable', **row,
            }
        else:
            current = grouped[key]
            for field in ('fecha_inicio', 'fecha_fin', 'plazo_ejecucion'):
                if field in row:
                    if field in current and current[field] != row[field]:
                        raise ValueError('Conflicting work dates or duration')
                    current[field] = row[field]
            for document in row['documentos']:
                if document not in current['documentos']:
                    current['documentos'].append(document)
    return list(grouped.values())


class CeheginAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-cehegin/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected source redirect')
        if self.config.get('evidence_dir'):
            path = Path(self.config['evidence_dir']) / capture
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        return response.content

    def backfill_proyectos(self, out_jsonl: Path):
        links = inventory_links(self._fetch(SOURCE, 'inventory.html'))
        rows = []
        for index, url in enumerate(links):
            rows.extend(parse_workbook(self._fetch(url, f'works-{index}.xlsx'), url))
        rows = group_works(rows)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE, *links],
                'coverage': 'partial municipal physical-works spreadsheet inventory; not current execution status'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
