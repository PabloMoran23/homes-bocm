"""Orio's public-exhibition inventory, including archived planning instruments."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://orio.eus/espedienteak/'
MONTHS = dict(zip('urtarrilaren otsailaren martxoaren apirilaren maiatzaren ekainaren uztailaren abuztuaren irailaren urriaren azaroaren abenduaren'.split(), range(1, 13)))


class OrioAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def next_page(html: str, page_url: str = SOURCE) -> str | None:
        soup = BeautifulSoup(html, 'html.parser')
        targets = set()
        for control in soup.select('a, link, button'):
            label = control.get_text(' ', strip=True).lower()
            if label in {'load more', 'gehiago kargatu'} or control.has_attr('data-next-page'):
                raise ValueError('Unsupported inventory continuation')
            if 'next' in control.get('rel', []) or label in {'next', 'siguiente', 'hurrengoa'}:
                target = urljoin(page_url, control.get('href', ''))
                parsed = urlparse(target)
                if parsed.hostname not in {'orio.eus', 'www.orio.eus'} or not re.fullmatch(r'/espedienteak/page/[1-9][0-9]*/', parsed.path) or parsed.query:
                    raise ValueError('Unexpected pagination target')
                targets.add(target)
        if len(targets) > 1:
            raise ValueError('Ambiguous pagination')
        if not targets and soup.select('.pagination a[href], .page-numbers[href]'):
            raise ValueError('Unrecognized pagination; review traversal')
        return next(iter(targets), None)

    @classmethod
    def parse_inventory(cls, html: str) -> list[dict]:
        cls.next_page(html)  # Validate controls; the fetch loop follows them.
        soup = BeautifulSoup(html, 'html.parser')
        rows = {}
        for block in soup.select('.accordion-item'):
            heading = block.select_one('h2.accordion-header')
            article = block.select_one('article.espe[id]')
            if not heading and not article and block.get_text(' ', strip=True) == 'Momentuan ez dago jendaurrean espedienterik irekita.':
                continue
            if not heading or not article:
                raise ValueError('Inventory accordion structure changed')
            title = heading.get_text(' ', strip=True)
            lower = title.lower()
            if 'ordenantza' in lower or 'araudi' in lower or 'arautegi' in lower:
                continue
            if lower.startswith('hiri antolamenduko plan orokorra'):
                kind = 'plan_general_ordenacion_urbana'
            elif lower.startswith('hapoaren aldaketa puntuala'):
                kind = 'modificacion_puntual_pgou'
            elif lower.startswith('hapoko ') and 'zonako plana' in lower:
                kind = 'plan_zonal_acustico'
            else:
                continue
            ident = article['id']
            if not ident.isdigit():
                raise ValueError('Missing stable municipal inventory identifier')
            content = article.select_one('.card-content')
            if content is None:
                raise ValueError('Missing instrument content')
            docs = {}
            for a in content.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if urlparse(url).hostname in {'orio.eus', 'www.orio.eus'} and '/wp-content/uploads/' in urlparse(url).path:
                    docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                          'source_url': SOURCE + '#flush-heading' + ident})
            if not docs:
                raise ValueError('Instrument has no municipal source documents')
            def exhibition_date(selector):
                el = article.select_one(selector)
                if not el:
                    raise ValueError('Missing public-exhibition period')
                return datetime.strptime(el.get_text(strip=True), '%Y/%m/%d').date().isoformat()
            description = '\n'.join(p.get_text(' ', strip=True) for p in content.select('p'))
            # Only an explicit council initial-approval sentence supports this date.
            match = re.search(r'(\d{4})ko (\w+) (\d{1,2})ko udalbatzarrean eman zion lehen onarpena', description)
            agreement = None
            if match and match[2] in MONTHS:
                agreement = datetime(int(match[1]), MONTHS[match[2]], int(match[3])).date().isoformat()
            row = {
                'id': 'orio-proy-' + ident, 'municipio': 'Orio', 'codigo_ine': '20061',
                'provincia': 'Gipuzkoa', 'titulo': title, 'tipo': kind,
                'url': SOURCE + '#flush-heading' + ident,
                'source': 'ayuntamiento', 'origen': 'inventario_expedientes_exposicion_publica',
                'descripcion': description, 'documentos': list(docs.values()),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': agreement,
                'fecha_inicio_exposicion': exhibition_date('.hasiera'),
                'fecha_fin_exposicion': exhibition_date('.amaiera'),
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
            if agreement:
                row['fase'] = 'aprobacion_inicial'
                row['fecha_acuerdo_proveniencia'] = description.split('\n')[0]
            if ident in rows and rows[ident] != row:
                raise ValueError('Conflicting duplicate inventory identifier')
            rows[ident] = row
        if not rows:
            raise ValueError('No supported instruments; review source before replacing snapshot')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        page_url = SOURCE
        seen = set()
        rows = {}
        while page_url:
            if page_url in seen or len(seen) >= 50:
                raise ValueError('Pagination cycle or safety limit; refusing partial output')
            seen.add(page_url)
            response = requests.get(page_url, timeout=40, headers={'User-Agent': 'Mozilla/5.0 (compatible; MunicipioOrio/1.0)'})
            response.raise_for_status()
            if response.url.rstrip('/') != page_url.rstrip('/'):
                raise ValueError('Unexpected inventory redirect')
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                name = 'inventory.html' if len(seen) == 1 else f'page-{len(seen)}.html'
                (capture / name).write_bytes(response.content)
            for row in self.parse_inventory(response.text):
                if row['id'] in rows and rows[row['id']] != row:
                    raise ValueError('Conflicting records between inventory pages')
                rows[row['id']] = row
            page_url = self.next_page(response.text, page_url)
        return {**self._write(out_jsonl, list(rows.values())), 'source_urls': sorted(seen), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
