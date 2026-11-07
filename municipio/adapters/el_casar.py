"""Complete snapshot of El Casar's municipal POM document inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://elcasar.es/areas-municipales/urbanismo'
HEADING = 'PLAN DE ORDENACIÓN MUNICIPAL VIGENTE EL CASAR'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Cobertura parcial: inventario municipal del POM y modificaciones, no todos los expedientes.',
    'Sin registro verificado de licencias concedidas; formularios, contratación y noticias excluidos.',
    'Sin fechas verificadas de aprobación del POM o su modificación; la fecha del BOP es de publicación.',
    'Sin coordenadas ni geometría verificadas; los planos PDF se conservan como documentos.',
    'Los documentos PDF se enlazan; su contenido no se interpreta automáticamente.',
]


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def _publication(text):
    match = re.search(r'BOP de Guadalajara de (\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    if not match:
        return None
    return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()


class ElCasarAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.cuerpoInterior')
        if content is None or [h.get_text(' ', strip=True) for h in content.select('h2')] != [HEADING]:
            raise ValueError('Missing or changed El Casar planning inventory')
        if soup.select('[rel~=next], .pagination, .pager') or any(
            a.get_text(' ', strip=True).lower() in {'siguiente', 'next', '»', 'cargar más', 'ver más'}
            for a in content.select('a[href]')):
            raise ValueError('Inventory pagination detected; crawler review required')
        blocks = content.find_all(['p', 'h3', 'h4'], recursive=False)
        if sum(len(b.select('a[href]')) for b in blocks) != len(content.select('a[href]')):
            raise ValueError('Unexpected nested document inventory; grouping review required')
        groups = [{'key': 'pom', 'title': HEADING, 'docs': {}, 'text': [], 'agreements': []}]
        for block in blocks:
            text = block.get_text(' ', strip=True)
            anchors = block.select('a[href]')
            modification = re.match(r'MODIFICACION N\s*[.º°o]*\s*(\d+) DEL PLAN DE ORDENACION MUNICIPAL DE EL CASAR', _norm(text), re.I)
            if modification:
                groups.append({'key': 'modificacion-' + modification[1], 'title': text,
                               'docs': {}, 'text': [], 'agreements': []})
            elif 'modificacion' in _norm(text) and anchors:
                raise ValueError('Unrecognized planning modification; grouping review required')
            group = groups[-1]
            if text:
                group['text'].append(text)
            if text.startswith('INTERPRETACIÓN DEL POM'):
                match = re.search(r'Acuerdo del Pleno (\d{2})/(\d{2})/(\d{4})', text)
                agreement_date = date(int(match[3]), int(match[2]), int(match[1])).isoformat() if match else None
                groups[0]['agreements'].append({'descripcion': text, 'fecha_acuerdo': agreement_date,
                                                'url_fuente': SOURCE})
                group['text'].pop()
            for a in anchors:
                url = urljoin(SOURCE, a['href'])
                parsed = urlsplit(url)
                if parsed.scheme != 'https' or parsed.netloc != 'elcasar.es' or not parsed.path.startswith('/media/') or not parsed.path.lower().endswith('.pdf'):
                    raise ValueError('Unexpected document link in planning inventory: ' + url)
                group['docs'].setdefault(url, {'titulo': a.get_text(' ', strip=True) or a.get('title', ''),
                                               'url': url, 'url_fuente': SOURCE})
        rows, seen = [], set()
        for group in groups:
            if group['key'] in seen or not group['docs']:
                raise ValueError('Duplicate instrument or instrument without documents')
            seen.add(group['key'])
            if group['key'] == 'pom' and not all(any(marker in _norm(d['titulo']) for d in group['docs'].values())
                                                for marker in ('documento i.', 'documento iii.', 'documento ii ')):
                raise ValueError('POM inventory lacks memory, rules or plans')
            rows.append({
                'id': 'el-casar-proy-' + hashlib.sha256((SOURCE + '#' + group['key']).encode()).hexdigest()[:16],
                'municipio': 'El Casar', 'provincia': 'Guadalajara', 'codigo_ine': '19071',
                'titulo': group['title'], 'tipo': 'planeamiento_urbanistico',
                'fase': 'vigente' if group['key'] == 'pom' else None,
                'fecha': None, 'fecha_publicacion': _publication(' '.join(group['text'])),
                'fecha_aprob': None, 'fecha_acuerdo': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'documentos': list(group['docs'].values()), 'acuerdos_vinculados': group['agreements'],
                'descripcion': '\n'.join(group['text']),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitations': LIMITATIONS,
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        request = Request(SOURCE, headers={'User-Agent': 'municipio-el-casar/1.0'})
        with urlopen(request, timeout=40) as response:
            if urlsplit(response.url).netloc != 'elcasar.es':
                raise ValueError('Unexpected source redirect')
            raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise ValueError('Inventory exceeds response size limit')
            html = raw.decode(response.headers.get_content_charset() or 'utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the full current inventory; no date cursor or page limit."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
