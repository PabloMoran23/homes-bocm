"""Municipal POM document inventory; a snapshot, not a register of approvals."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.almodovardelcampo.es/plan-de-ordenacion-municipal/'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article')
    heading = article.select_one('h1.entry-title') if article else None
    content = article.select_one('.entry-content') if article else None
    if not heading or not content:
        raise ValueError('Missing municipal plan content')
    title = heading.get_text(' ', strip=True)
    if 'Plan de Ordenación Municipal' not in title or '2ª Información Pública' not in title:
        raise ValueError('Unexpected instrument or consultation stage')
    # A single plan page is the complete supported inventory. Never accept a
    # split inventory as a complete snapshot without implementing its traversal.
    if soup.select('a[rel~=next], .pagination a, .page-links a, .nav-links a.next'):
        raise ValueError('Unexpected pagination: inventory requires review')
    paragraphs = [p.get_text(' ', strip=True) for p in content.select('p') if p.get_text(strip=True)]
    narrative = '\n'.join(paragraphs)
    if 'Ayuntamiento de Almodóvar del Campo' not in narrative or 'Informe de Sostenibilidad Ambiental' not in narrative:
        raise ValueError('Missing municipality or environmental plan narrative')
    documents = []
    seen = set()
    for table in content.select('table'):
        if 'Documento PDF disponible' not in table.get_text(' ', strip=True):
            continue
        for a in table.select('tbody a[href]'):
            url = urljoin(source_url, a['href'])
            label = a.get_text(' ', strip=True)
            if not label or urlparse(url).scheme != 'https' or not urlparse(url).hostname:
                raise ValueError('Invalid plan document link')
            if url not in seen:
                documents.append({'titulo': label, 'url': url, 'inventory_url': source_url,
                                  'verification': 'linked_by_municipality; document_content_not_verified'})
                seen.add(url)
    labels = ' '.join(d['titulo'] for d in documents)
    if not documents or not all(label in labels for label in ('MEMORIA INFORMATIVA', 'NORMAS URBANÍSTICAS', 'PLANOS ORDENACIÓN')):
        raise ValueError('Missing technical POM document inventory')
    # Only this explicit consultation-start narrative supplies a date. Neither
    # WordPress timestamps nor dates of quoted legislation establish approval.
    match = re.search(r'a contar desde el (\d{1,2}) de (\w+) de (\d{4})', narrative)
    exposure = None
    if match and match[2] in MONTHS:
        exposure = date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()
    return [{
        'id': 'almodovar-del-campo-pom-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Almodóvar del Campo', 'codigo_ine': '13015', 'provincia': 'Ciudad Real',
        'titulo': title, 'tipo': 'Plan de Ordenación Municipal',
        'fase': 'segunda información pública (según página municipal; vigencia actual no verificada)',
        'descripcion': narrative, 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None, 'fecha_inicio_informacion_publica': exposure,
        'url': source_url, 'inventory_url': source_url, 'documentos': documents,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pom',
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
        'coverage': 'single published POM consultation package; not all municipal projects or current legal status',
    }]


class AlmodovarDelCampoAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=45, stream=True, headers={
            'User-Agent': 'municipio-almodovar-del-campo/1.0',
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
                raise ValueError('Unexpected source redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML inventory')
            payload = bytearray()
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 4_000_000:
                    raise ValueError('Inventory response too large')
            rows = parse_inventory(payload.decode('utf-8'), response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pom.html').write_bytes(payload)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'source_sha256': hashlib.sha256(payload).hexdigest(),
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'single_page_pom_package', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
