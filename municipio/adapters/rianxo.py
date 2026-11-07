"""Rianxo's municipal PXOM document inventory (one instrument, multiple phases)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://concelloderianxo.gal/pxom'
HOSTS = {'concelloderianxo.gal', 'sede.concelloderianxo.gal'}
MONTHS = dict(zip(('xaneiro', 'febreiro', 'marzo', 'abril', 'maio', 'xuño',
                   'xullo', 'agosto', 'setembro', 'outubro', 'novembro', 'decembro'), range(1, 13)))


def clean(text):
    return ' '.join(text.replace('\u200b', '').replace('\ufeff', '').split())


def canonical(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))


def parse_page(html, url, phase):
    """Read every attachment in the relevant journal article; reject pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href], button'):
        label = clean(a.get_text(' ', strip=True)).casefold()
        aria = str(a.get('aria-label', '')).casefold()
        if ('next' in a.get('rel', []) or label in {'seguinte', 'siguiente', 'next', '›', '»'}
                or aria in {'next', 'siguiente', 'seguinte'}):
            raise ValueError('PXOM inventory has pagination; traversal must be reviewed')
    marker = 'Documento de aprobación ' + phase
    blocks = [b for b in soup.select('.journal-content-article')
              if marker.casefold() in clean(b.get_text(' ', strip=True)).casefold()]
    if not blocks:
        raise ValueError('Expected PXOM document article missing')
    documents = {}
    previous = {canonical(urljoin(url, a['href']))
                for block in soup.select('.journal-content-article')
                for a in block.select('a[href]')
                if phase == 'provisional'
                and clean(a.get_text(' ', strip=True)) == 'Documento de aprobación inicial'
                and urlparse(urljoin(url, a['href'])).hostname in HOSTS}
    agreement = None
    for block in blocks:
        text = clean(block.get_text(' ', strip=True))
        if phase == 'provisional':
            match = re.search(r'aprobado provisionalmente na sesión do Pleno da Corporación do '
                              r'(\d{1,2}) de (\w+) de (\d{4})', text)
            if not match:
                raise ValueError('Provisional agreement statement changed')
            agreement = date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
        for a in block.select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            if parsed.scheme not in {'https', 'http'} or parsed.hostname not in HOSTS:
                continue
            title = clean(a.get_text(' ', strip=True))
            if not re.search(r'\.(pdf|zip)(?:/|$)', parsed.path, re.I):
                continue
            # Blank image anchors also carry real A3 plan attachments.
            title = title or parsed.path.split('/')[-2 if '/documents/' in parsed.path else -1]
            key = canonical(target)
            documents.setdefault(key, {'titulo': title, 'url': target, 'fase_documental': phase,
                                       'source_url': url, 'provenance': 'enlace_en_inventario_municipal'})
    if not documents:
        raise ValueError('No PXOM attachments found')
    return list(documents.values()), sorted(previous), agreement


class RianxoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-rianxo/1.0 (public planning inventory)'})
        response.raise_for_status()
        if canonical(response.url) != canonical(url):
            raise ValueError('Unexpected PXOM inventory redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (urlparse(url).path.strip('/').replace('/', '_') + '.html')).write_text(
                response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        docs, previous, agreement = parse_page(self._fetch(SOURCE), SOURCE, 'provisional')
        sources = [SOURCE]
        for url in previous:
            older, further, _ = parse_page(self._fetch(url), url, 'inicial')
            if further:
                raise ValueError('Additional historical phases require traversal review')
            docs.extend(older)
            sources.append(url)
        # The prior-phase link is part of the reviewed inventory, not an optional fetch.
        if not previous:
            raise ValueError('Initial-phase inventory link disappeared')
        row = {'id': 'rianxo-pxom', 'municipio': 'Rianxo', 'codigo_ine': '15072',
               'provincia': 'A Coruña', 'titulo': 'Plan Xeral de Ordenación de Rianxo',
               'tipo': 'planeamiento_urbanistico', 'fase': 'aprobacion_provisional',
               'fecha_acuerdo': agreement, 'url': SOURCE, 'source': 'ayuntamiento',
               'origen': 'inventario_documental_pxom', 'source_urls': sources,
               'documentos': list({canonical(d['url']): d for d in docs}.values()),
               'geometry_status': 'unavailable', 'publication_ready': False,
               'coverage': 'PXOM y documentos de fases provisional e inicial; no inventario municipal exhaustivo',
               'estado_segun_fuente': 'Documento provisional remitido a la Xunta; sin verificación de aprobación definitiva'}
        result = self._write(out_jsonl, [row])
        return {**result, 'source_urls': sources, 'coverage': row['coverage']}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of this small, nonpaginated document inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
