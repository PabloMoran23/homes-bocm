"""Oza-Cesuras physical works in the official provincial Plan Único inventory."""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://plan-unico.dacoruna.gal/oza-cesuras/'


def _money(text: str) -> str:
    text = text.replace('\xa0', ' ').strip()
    if not re.fullmatch(r'\d{1,3}(?:\.\d{3})*,\d{2}\s*€|\d+,\d{2}\s*€', text):
        raise ValueError(f'Unrecognized euro amount: {text!r}')
    try:
        return str(Decimal(text.replace('€', '').replace(' ', '').replace('.', '').replace(',', '.')))
    except InvalidOperation as exc:
        raise ValueError('Invalid budget') from exc


class OzaCesurasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='oza-cesuras', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('h1')
        if not heading or heading.get_text(' ', strip=True) != 'PLAN ÚNICO Oza-Cesuras':
            raise ValueError('Unexpected municipality or missing Plan Único inventory')
        # The reviewed source embeds all years in one HTML response. Fail closed
        # if a later version adds navigation requiring a different traversal.
        for link in soup.select('a[href]'):
            label = link.get_text(' ', strip=True).casefold()
            rel = link.get('rel', [])
            if ('next' in rel or label in {'seguinte', 'siguiente', 'next', 'máis', 'ver máis', 'cargar máis'}
                    or re.search(r'[?&](?:page|pagina|offset)=', link['href'])):
                raise ValueError('Pagination detected; traversal must be reviewed')
        totals = [li for li in soup.select('li')
                  if li.find('span', string='Obras aprobadas')]
        if len(totals) != 1:
            raise ValueError('Missing or ambiguous approved works total')
        total = re.fullmatch(r'Obras aprobadas\s+(\d+)', totals[0].get_text(' ', strip=True))
        if not total:
            raise ValueError('Unrecognized approved works total')
        rows, seen, years = [], set(), set()
        for title_node in soup.select('p.text-sm.font-medium.leading-tight.mb-4'):
            card = title_node.parent.parent
            year_node = card.select_one('span.uppercase')
            year_match = re.fullmatch(r'Exercicio\s+(\d{4})', year_node.get_text(' ', strip=True)) if year_node else None
            if not year_match:
                raise ValueError('Work without fiscal year')
            year = int(year_match[1])
            years.add(str(year))
            title = title_node.get_text(' ', strip=True)
            if not title:
                raise ValueError('Work without denomination')
            amounts = {}
            for label in card.select('span'):
                key = label.get_text(' ', strip=True)
                if key in {'Orzamento:', 'Aportación:'}:
                    value = label.find_next_sibling('span')
                    if key in amounts or value is None:
                        raise ValueError('Ambiguous work amounts')
                    amounts[key] = _money(value.get_text(' ', strip=True))
            if set(amounts) != {'Orzamento:', 'Aportación:'}:
                raise ValueError('Missing work amounts')
            # No upstream work ID is published. Identity excludes mutable amounts
            # and card order. Duplicate same-year titles require manual review.
            identity = f'{year}|{title}'
            if identity in seen:
                raise ValueError('Ambiguous duplicate work in fiscal year')
            seen.add(identity)
            documents = []
            for a in card.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if url not in {d['url'] for d in documents}:
                    documents.append({'titulo': a.get_text(' ', strip=True), 'url': url})
            rows.append({
                'id': 'oza-cesuras-pos-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
                'municipio': 'Oza-Cesuras', 'codigo_ine': '15902', 'provincia': 'A Coruña',
                'titulo': title, 'tipo': 'obra_publica', 'fase': 'aprobada en Plan Único',
                'ejercicio': year, 'presupuesto_eur': amounts['Orzamento:'],
                'aportacion_eur': amounts['Aportación:'],
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'diputacion', 'organismo_fuente': 'Deputación da Coruña',
                'origen': 'plan_unico_obras_aprobadas', 'documentos': documents,
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False,
            })
        if not rows or len(rows) != int(total[1]):
            raise ValueError(f'Incomplete inventory: parsed {len(rows)}, declared {total[1]} works')
        options = {o.get_text(strip=True) for o in soup.select('select option')
                   if re.fullmatch(r'\d{4}', o.get_text(strip=True))}
        if options and not years.issubset(options):
            raise ValueError('Unexpected year outside inventory selector')
        return sorted(rows, key=lambda r: (-r['ejercicio'], r['titulo']))

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-oza-cesuras/1.0')})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected source redirect')
        rows = self.parse_projects(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'plan-unico.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh every fiscal year; no incremental date is exposed by this source.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
