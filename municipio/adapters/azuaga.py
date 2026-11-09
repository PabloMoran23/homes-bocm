"""Azuaga's municipal planning documents, grouped by instrument (not licences)."""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://azuaga.es/plantilla.php?enlace=normativa'
LIMITATIONS = [
    'Partial coverage: only the Normas Subsidiarias documents in Normativa y Solicitudes; no complete planning history or public-works inventory.',
    'Fecha de Alta is document upload metadata, not publication of a legal notice or an agreement/approval date.',
    'Current legal validity and approval dates are not established by this inventory.',
    'Scanned PDF and PDF plans in ZIP; no verified vector geometry or coordinates.',
    'Licence applications, tax ordinances, procurement and unrelated notices are excluded; licences disabled.',
]


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


class AzuagaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.contenidop')
        if content is None or 'Normativa y Solicitudes' not in content.get_text(' ', strip=True):
            raise ValueError('Municipal document inventory missing or changed')
        # This source is a complete, unpaginated document section. Fail closed if
        # navigation appears, rather than silently accepting its first page.
        for a in content.select('a[href]'):
            query = parse_qs(urlparse(a['href']).query)
            label = _norm(a.get_text(' ', strip=True))
            if query.keys() & {'ini', 'page', 'pagina', 'offset', 'start'} or label in {'siguiente', 'siguientes', 'ultima', 'next'} or 'next' in a.get('rel', []):
                raise ValueError('Inventory pagination requires review before extraction')
        refs = []
        docs = {}
        roles = set()
        for a in content.select('a[href]'):
            title = a.get_text(' ', strip=True)
            key = _norm(title)
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if key == 'normas subsidiarias de azuaga' and parsed.hostname == 'sitex.juntaex.es':
                refs.append({'titulo': title, 'url': url, 'tipo': 'portal_autonomico_general'})
                continue
            if key not in {'normas subsidiarias', 'planos normas subsidiarias de azuaga'}:
                continue
            role = 'planos' if key.startswith('planos') else 'normativa'
            suffix = '.zip' if role == 'planos' else '.pdf'
            if parsed.scheme != 'https' or parsed.hostname not in {'azuaga.es', 'www.azuaga.es'} or not parsed.path.startswith('/documentos/') or not parsed.path.lower().endswith(suffix):
                raise ValueError('Unexpected planning document location/type')
            block = a.find_parent('div')
            match = re.search(r'Fecha de Alta:\s*(\d{2}/\d{2}/\d{4})', block.get_text(' ', strip=True))
            uploaded = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None
            doc = {'titulo': title, 'url': url, 'tipo': role, 'fecha_alta': uploaded,
                   'fecha_alta_significado': 'Fecha de Alta del documento en el portal municipal',
                   'source_url': SOURCE}
            if url in docs and docs[url] != doc:
                raise ValueError('Conflicting metadata for planning document')
            docs[url] = doc
            roles.add(role)
        if roles != {'normativa', 'planos'}:
            raise ValueError('Expected Normas Subsidiarias and associated plans; inventory incomplete')
        return [{
            'id': 'azuaga-proy-normas-subsidiarias', 'municipio': 'Azuaga',
            'codigo_ine': '06014', 'provincia': 'Badajoz',
            'titulo': 'Normas Subsidiarias de Azuaga', 'tipo': 'planeamiento_urbanistico',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_normativa',
            'documentos': sorted(docs.values(), key=lambda d: d['url']),
            'enlaces_relacionados': sorted(refs, key=lambda d: d['url']),
            'descripcion': 'Instrumento de planeamiento publicado en Normativa y Solicitudes; normativa y planos agrupados. No se acredita aquí su vigencia ni fecha de aprobación.',
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'limitations': LIMITATIONS,
        }]

    def _fetch(self, url, limit):
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipio-azuaga/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'azuaga.es', 'www.azuaga.es'}:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds response size bound; nothing written')
                chunks.append(chunk)
            return b''.join(chunks)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        html = self._fetch(SOURCE, 2_000_000)
        rows = self.parse_inventory(html)
        captures = {'inventory.html': html}
        for doc in rows[0]['documentos']:
            data = self._fetch(doc['url'], 30_000_000)
            if doc['tipo'] == 'normativa':
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Normativa link no longer returns PDF')
            else:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    names = archive.namelist()
                    if not any(n.lower().endswith('.pdf') for n in names):
                        raise ValueError('Planning archive lacks PDF plans')
                    doc['archivos'] = names
            doc['sha256'] = hashlib.sha256(data).hexdigest()
            doc['bytes'] = len(data)
            captures[Path(urlparse(doc['url']).path).name] = data
        evidence = self.config.get('evidence_dir')
        if evidence:
            evidence = Path(evidence)
            evidence.mkdir(parents=True, exist_ok=True)
            for name, data in captures.items():
                (evidence / name).write_bytes(data)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [d['url'] for d in rows[0]['documentos']], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Small current document inventory: full refresh, no fictitious cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
