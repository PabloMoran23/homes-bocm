"""Named planning proceedings from Alcalá la Real's municipal urbanismo page."""
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


class AlcalaLaRealAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = 'https://alcalalareal.es/urbanismo-y-patrimonio-municipal/'

    @staticmethod
    def parse_projects(html: str, slug: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        records = []
        for panel in soup.select('.vc_tta-panel'):
            heading = panel.select_one('.vc_tta-panel-title')
            title = heading.get_text(' ', strip=True) if heading else ''
            # Only named proceedings: exclude the general PGOU library, navigation,
            # contact details, reusable procedures and municipal regulations.
            if not re.match(r'^Plan (?:Parcial|parcial|Especial)\b', title):
                continue
            body = panel.select_one('.vc_tta-panel-body')
            if body is None:
                raise ValueError(f'Missing proceeding body: {title}')
            description = body.get_text(' ', strip=True)
            if not re.search(r'informaci[oó]n p[uú]blica|someter a consulta', description, re.I):
                continue
            documents = []
            for link in body.select('a[href]'):
                href = urljoin(AlcalaLaRealAyuntamientoAdapter.SOURCE, link['href'])
                if not urlparse(href).scheme in {'http', 'https'}:
                    continue
                # The electronic-office URL is an allegation channel, not a document.
                if ('sedelectronica.es' in urlparse(href).netloc
                        or urlparse(href).path in {'', '/'}):
                    continue
                text = link.get_text(' ', strip=True)
                if text and href not in {d['url'] for d in documents}:
                    documents.append({'titulo': text, 'url': href})
            if not documents:
                raise ValueError(f'No source documents for {title}')
            identity = re.sub(r'\s+', ' ', title).strip().casefold()
            row = {
                'id': f'{slug}-proy-{hashlib.sha256(identity.encode()).hexdigest()[:14]}',
                'municipio': 'Alcalá la Real', 'titulo': title,
                'tipo': 'plan_especial' if 'Especial' in title else 'plan_parcial',
                'fecha': None, 'source': 'ayuntamiento',
                'origen': 'expediente_planeamiento_municipal',
                'url': AlcalaLaRealAyuntamientoAdapter.SOURCE + '#' + panel['id'],
                'descripcion': description, 'descripcion_source_url': AlcalaLaRealAyuntamientoAdapter.SOURCE,
                'documentos': documents,
            }
            # An agreement date is not a publication date; never infer dates from
            # upload paths, page metadata, unrelated statutory dates or scrape time.
            match = re.search(r'(?:sesi[oó]n ordinaria celebrada el d[ií]a|Fecha del acuerdo:)\s*(\d{2}/\d{2}/\d{4})', description, re.I)
            if match:
                row['fecha_acuerdo'] = datetime.strptime(match.group(1), '%d/%m/%Y').date().isoformat()
            if re.search(r'aprobaci[oó]n inicial|aprobado inicialmente', description, re.I):
                row['fase'] = 'aprobacion_inicial'
            records.append(row)
        if not records:
            raise ValueError('No named planning proceedings found; inspect municipal page layout')
        return records

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'rows': len(rows), 'status': 'ok'}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(self.SOURCE, timeout=30, headers={
            'User-Agent': self.config.get('user_agent', 'poc-bocm-alcala-la-real/1.0')})
        response.raise_for_status()
        return self._write(out_jsonl, self.parse_projects(response.text, self.slug))

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        # The page describes licence competences but contains no grant register.
        return self._write(out_jsonl, [])

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
