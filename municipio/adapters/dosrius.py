"""Dosrius' municipal public-information inventory, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/dosrius/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/'
          'projectes-d-obres-locals-i-instruments-de-planejament-en-tramit-204')


def _text(node):
    # Joining inline spans without spaces repairs the source's split "P"/"rojecte".
    return ' '.join(node.get_text().split())


def _key(title):
    normalized = re.sub(r'[^\w]+', ' ', title.casefold()).strip()
    # The inventory repeats the Can Batlle municipal library under two names.
    if 'biblioteca' in normalized and 'can batlle' in normalized:
        return 'biblioteca municipal can batlle'
    return normalized


class DosriusAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        candidates = [n for n in soup.select('.journal-content-article')
                      if 'informació pública general' in n.get_text() and n.select('a[href*="/documents/1218885/"]')]
        if len(candidates) != 1:
            raise ValueError('Expected one Dosrius project inventory, not a login or navigation page')
        root = candidates[0]
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if (a.get('rel') and 'next' in a['rel']) or label in {'següent', 'siguiente', 'next', 'següent pàgina'}:
                if a['href'] not in {'', '#'}:
                    raise ValueError('Pagination detected; crawler must be extended before extracting')
        if root.select('.pagination, .lfr-pagination, .taglib-page-iterator'):
            raise ValueError('Unreviewed pagination in inventory')
        groups, current, year = [], None, None
        for node in root.descendants:
            if not isinstance(node, Tag):
                continue
            if node.name in {'p', 'h4', 'div'} and not node.find(['p', 'h4', 'div']):
                text = _text(node)
                heading = re.fullmatch(r'[Pp]?rojectes Urbanístics any (\d{4})', text)
                if heading:
                    year, current = int(heading[1]), None
                    continue
                if text.startswith('-') and not re.match(r'^-\s*(?:Descarrega|Descàrrega|Desacrrega|Decarrega)', text, re.I):
                    title = text.lstrip('- ').strip()
                    # Every section item terminates the previous item, even if excluded.
                    current = None
                    supported = re.match(r'^(Projecte\b|Modificació\b|Normes subsidiàries\b|Aprovació inc?ial\b|Aprovació inicial\b|Millora de seguretat viaria\b)', title, re.I)
                    if supported:
                        if year is None:
                            raise ValueError('Project outside a dated inventory section')
                        current = {'titulo': title, 'titulos_fuente': [title], 'anios_seccion': [year],
                                   'documentos': [], 'texto_fuente': [text]}
                        groups.append(current)
            if node.name == 'a' and ('/documents/1218885/' in node.get('href', '')
                                     or '/media/repository/' in node.get('href', '')):
                if current is None:
                    continue
                url = urljoin(SOURCE, node['href'])
                if urlparse(url).hostname not in {'seu-e.cat', 'www.seu-e.cat', 'dosrius.webmunicipal.diba.cat', 'www.dosrius.cat'}:
                    raise ValueError('Unexpected document host')
                context = node.find_parent('li') or node.parent
                current['documentos'].append({'titulo': node.get_text(' ', strip=True),
                                              'contexto': context.get_text(' ', strip=True), 'url': url,
                                              'enlace_en_titulo': bool(re.match(r'^-\s*(?:Projecte|Modificació|Normes|Aprovació|Millora)\b', node.get_text(strip=True), re.I)),
                                              'url_origen': SOURCE})
                current['texto_fuente'].append(context.get_text(' ', strip=True))
        if not groups or any(not g['documentos'] for g in groups):
            raise ValueError('Empty inventory or project without linked documents')
        # Repeated titles across years and repeated document UUIDs are the same
        # instrument. Distinct annual road projects remain distinct.
        merged = []
        def identities(g):
            return {urlparse(d['url']).path.rsplit('/', 1)[-1] for d in g['documentos']
                    if not d['enlace_en_titulo']}
        for group in groups:
            matches = [g for g in merged if set(map(_key, g['titulos_fuente'])) & set(map(_key, group['titulos_fuente']))
                       or identities(g) & identities(group)]
            for old in matches:
                merged.remove(old)
                for field in ('titulos_fuente', 'anios_seccion', 'documentos', 'texto_fuente'):
                    group[field].extend(v for v in old[field] if v not in group[field])
            merged.append(group)
        rows = []
        for group in merged:
            titles = ' '.join(group['titulos_fuente'])
            narrative = ' '.join(group['texto_fuente'])
            agreement_dates = set()
            for match in re.finditer(r'(?:sessió de (?:Ple municipal de )?(?:data )?)(\d{2}/\d{2}/\d{4})', narrative):
                agreement_dates.add(datetime.strptime(match[1], '%d/%m/%Y').date().isoformat())
            # No date is taken from annual headings, page updates or PDF filenames.
            agreement = next(iter(agreement_dates)) if len(agreement_dates) == 1 else None
            phase = 'aprobación inicial' if re.search(r'aprov(?:ació|at)\s+inc?ial|aprov(?:ació|at)\s+inicial', narrative, re.I) else None
            reference = re.search(r'exp(?:\s+absis)?\s+(\d+[/\-]\d{4})', titles, re.I)
            doc_ids = sorted(identities(group))
            if not doc_ids:
                raise ValueError('Project has only a title hyperlink, no supporting documents')
            rows.append({
                'id': 'dosrius-proy-' + hashlib.sha256(doc_ids[0].encode()).hexdigest()[:16],
                'municipio': 'Dosrius', 'codigo_ine': '08075', 'provincia': 'Barcelona',
                'titulo': group['titulo'], 'titulos_fuente': group['titulos_fuente'],
                'tipo': 'planeamiento_urbanistico' if re.search(r'NNSS|normes subsidiàries', titles, re.I) else 'proyecto_obra_publica',
                'fase': phase, 'expediente': reference[1] if reference else None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': agreement,
                'fecha_aprob': agreement if phase else None,
                'anios_seccion': sorted(group['anios_seccion']),
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_informacion_publica',
                'documentos': group['documentos'], 'descripcion': '\n'.join(group['texto_fuente']),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            })
        return sorted(rows, key=lambda row: row['id'])

    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'municipio-dosrius/1.0'})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError('Unexpected inventory response size')
        rows = self.parse_projects(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        # Complete inventory refresh; no watermark can hide edits to older sections.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
