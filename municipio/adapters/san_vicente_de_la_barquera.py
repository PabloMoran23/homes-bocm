"""Municipal planning inventory snapshot, not a register of granted licences."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://aytosanvicentedelabarquera.es/urbanismo/'


def _label_date(text, label):
    match = re.search(label + r'\s*:\s*(\d{1,2}/\d{1,2}/\d{4})(?!\d)', text, re.I)
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None


def _documents(content):
    docs = {}
    for a in content.select('a[href]'):
        url = urljoin(SOURCE, a['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            raise ValueError(f'Unexpected inventory attachment: {url}')
        if urlparse(url).hostname != urlparse(SOURCE).hostname:
            raise ValueError(f'Unreviewed attachment host: {url}')
        docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                              'url_origen': SOURCE})
    if not docs:
        raise ValueError('Planning instrument has no document links')
    return list(docs.values())


class SanVicenteDeLaBarqueraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        # This is a single accordion inventory. Stop if it becomes paginated;
        # never emit the first page as a complete inventory.
        if soup.select('a[rel~=next], .pagination, .nav-links, .page-numbers'):
            raise ValueError('Inventory pagination requires crawler review')
        for a in soup.select('a[href]'):
            if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', '»'}:
                raise ValueError('Possible inventory pagination requires review')
        items = [i for i in soup.select('.elementor-toggle-item')
                 if not i.find_parent(class_='elementor-toggle-item')]
        rows, criteria = {}, []
        for item in items:
            heading = item.select_one('.elementor-tab-title')
            content = item.select_one('.elementor-tab-content')
            if heading is None or content is None:
                raise ValueError('Changed accordion structure')
            title = heading.get_text(' ', strip=True)
            text = content.get_text(' ', strip=True)
            low = title.casefold()
            if low.startswith('criterios de interpretación. pgou'):
                criteria = _documents(content)
                continue
            if ('constitución junta de compensación' in low
                    or low.startswith('plan de ordenación de los recursos naturales')):
                continue  # organisational act / regional multi-municipality plan
            approval = publication = None
            phase = None
            match = re.match(r'Expediente (\d+/\d{4})[.:]', title)
            expediente = match[1] if match else None
            if 'estudio de detalle' in low:
                kind = 'estudio_de_detalle'
                key = expediente or low
                # Only explicit document labels establish the published stage.
                labels = ' '.join(a.get_text(' ', strip=True) for a in content.select('a[href]')).casefold()
                if 'aprobación definitiva' in labels or 'aprobado definitivamente' in labels:
                    phase = 'aprobación definitiva'
                elif 'aprobación inicial' in labels or 'aprob. inicial' in labels:
                    phase = 'aprobación inicial'
            elif low.startswith('pgou san vicente'):
                kind, key = 'plan_general', 'pgou'
                approval = _label_date(text, 'Aprobación CROTU')
                publication = _label_date(text, 'Publicación BOC')
            elif low.startswith('plan especial de protección y reforma interior'):
                kind, key = 'plan_especial', 'pepri'
                approval = _label_date(text, 'Aprobación CROTU')
                publication = _label_date(text, 'Publicación BOC')
            elif low.startswith('catálogo de edificaciones en suelo rústico'):
                kind, key = 'catalogo_edificaciones', 'cesr'
                # The dates belong to the title, not to upload paths or PDFs.
                for pattern, field in [(r'Aprobado.*?del (\d{1,2}) de (\w+) de (\d{4})', 'approval'),
                                       (r'publicado BOC del (\d{1,2}) de (\w+) de (\d{4})', 'publication')]:
                    m = re.search(pattern, title, re.I)
                    if m:
                        months = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
                        value = datetime(int(m[3]), months.index(m[2].lower()) + 1, int(m[1])).date().isoformat()
                        if field == 'approval':
                            approval = value
                        else:
                            publication = value
            else:
                raise ValueError(f'Unreviewed top-level inventory section: {title}')
            if key in rows:
                raise ValueError(f'Duplicate instrument identity: {key}')
            rows[key] = {
                'id': 'san-vicente-de-la-barquera-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'San Vicente de la Barquera', 'provincia': 'Cantabria',
                'codigo_ine': '39080', 'titulo': title, 'expediente': expediente,
                'tipo': kind, 'fase': phase, 'fecha': None,
                'fecha_acuerdo': approval, 'fecha_publicacion': publication,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
                'documentos': _documents(content),
                'fechas_fuente': title if kind == 'catalogo_edificaciones' else text.split('Memoria')[0] if kind in {'plan_general', 'plan_especial'} else None,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitaciones': 'Inventario parcial; fechas no explícitas en HTML y geometrías no extraídas. Documentos enlazados, no interpretados.',
            }
        if not rows or 'pgou' not in rows:
            raise ValueError('Missing municipal planning inventory / PGOU')
        if criteria:
            rows['pgou']['documentos_complementarios'] = criteria
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'municipio-san-vicente-de-la-barquera/1.0'})
        response.raise_for_status()
        rows = self.parse_projects(response.text)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'coverage': 'partial'}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current-inventory refresh; state is not a date filter.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
