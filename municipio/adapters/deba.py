"""Deba's municipal development-planning inventory, one record per instrument."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


class DebaAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = 'https://www.deba.eus/es/ayuntamiento/normativa-municipal/normas-subsidiarias/'
    LIMITATIONS = [
        'Cobertura parcial: solo planeamiento de desarrollo y programas/proyectos de '
        'gestión de las secciones Deba, Itziar y Lastur del inventario municipal.',
        'No incluye NNSS generales, modificaciones fuera de esas secciones, convenios, '
        'ordenanzas, noticias, contratación ni un registro de licencias concedidas.',
        'Las fechas de publicación, acuerdo y aprobación no se deducen de URLs, '
        'nombres de archivo ni de la presencia de documentos de aprobación.',
        'Se conservan todos los enlaces documentales descubiertos; salvo el PDF '
        'directo del inventario, no se comprueba la disponibilidad de cada archivo. '
        'Hay enlaces heredados y documentación técnica sin enlace en algunas páginas.',
        'Los documentos del servidor interno backend:8080/Plone se expresan en el '
        'dominio público municipal, conservando el href publicado.',
        'Sin geometría vectorial verificada ni coordenadas; la presencia en el '
        'inventario no garantiza vigencia consolidada ni ejecución material.',
        'Actualización por instantánea completa del ámbito cubierto; no hay '
        'inventario exhaustivo de obras ni histórico incremental de cambios.',
    ]

    @staticmethod
    def public_url(href, parent):
        parsed = urlsplit(urljoin(parent, href))
        # The municipal frontend leaks its Plone container URL in download links.
        if parsed.netloc == 'backend:8080' and parsed.path.startswith('/Plone/'):
            parsed = urlsplit('https://www.deba.eus/' + parsed.path[len('/Plone/'):])
        if parsed.scheme not in {'http', 'https'} or parsed.hostname not in {
            'www.deba.eus', 'deba.eus', 'ssl4.gipuzkoa.net', 'www.gipuzkoa.eus'
        }:
            raise ValueError(f'Unexpected source link: {href}')
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))

    @staticmethod
    def content(html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main')
        if main is None or main.select_one('h1') is None:
            raise ValueError('Municipal content missing (HTTP error or layout change)')
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if (a.get('href', '').strip() not in {'', '#'} and
                ('next' in a.get('rel', []) or label in {
                    'siguiente', 'siguiente página', 'next', 'hurrengoa', '»', '›'
                })):
                raise ValueError('Pagination detected; review crawler before accepting partial inventory')
        if main.select('.pagination, .batching, .pager'):
            raise ValueError('Pagination controls detected; inventory requires review')
        return main

    @classmethod
    def parse_inventory(cls, html):
        main = cls.content(html)
        if main.select_one('h1').get_text(' ', strip=True) != 'Normas Subsidiarias':
            raise ValueError('Unexpected inventory title')
        sections = main.select('.accordion-block .accordion')
        if {s.select_one('h2').get_text(' ', strip=True) for s in sections} != {
            'Deba', 'Itziar', 'Lastur'
        }:
            raise ValueError('Development-planning sections changed')
        rows = {}
        for section in sections:
            area = section.select_one('h2').get_text(' ', strip=True)
            for a in section.select('li a[href]'):
                title = a.get_text(' ', strip=True)
                if not title or title.upper().startswith('CONVENIO'):
                    continue
                if not title.upper().startswith(('PLAN ', 'MODIFICACIÓN PERI ',
                                                 'FORMULACION DEL PLAN ',
                                                 'PROGRAMA DE ACTUACIÓN ',
                                                 'PROYECTO DE REPARCELACION ')):
                    raise ValueError(f'Unclassified development instrument: {title}')
                url = cls.public_url(a['href'], cls.SOURCE)
                if url in rows:
                    continue
                kind = ('reparcelacion' if title.startswith('PROYECTO DE REPARCELACION')
                        else 'programa_actuacion_urbanizadora' if title.startswith('PROGRAMA')
                        else 'planeamiento_urbanistico')
                rows[url] = {
                    'id': 'deba-proy-' + hashlib.sha256(url.encode()).hexdigest()[:20],
                    'municipio': 'Deba', 'codigo_ine': '20029', 'provincia': 'Gipuzkoa',
                    'titulo': title, 'tipo': kind, 'ambito': area,
                    'url': url, 'source': 'ayuntamiento',
                    'source_url': cls.SOURCE,
                    'origen': 'inventario_municipal_planeamiento_desarrollo',
                    'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'documentos': [], 'href_inventario': a['href'],
                }
        if not rows:
            raise ValueError('Empty development-planning inventory')
        return list(rows.values())

    @classmethod
    def parse_documents(cls, html, parent):
        main = cls.content(html)
        docs = {}
        for a in main.select('a[href]'):
            title = a.get_text(' ', strip=True)
            if not title or a.get('aria-hidden') == 'true' or a['href'].startswith('#'):
                continue
            url = cls.public_url(a['href'], parent)
            if url == parent:
                continue
            docs.setdefault(url, {
                'titulo': title, 'url': url, 'href_publicado': a['href'],
                'source_url': parent, 'access_status': 'not_checked',
            })
        if not docs:
            raise ValueError(f'Instrument has no linked documentation: {parent}')
        return list(docs.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                        encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('evidence_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (municipal-planning-research/1.0)'

            def fetch(url, pdf=False):
                time.sleep(.25)
                response = session.get(url if pdf else url.rstrip('/') + '/', timeout=35)
                response.raise_for_status()
                if pdf and not response.content.startswith(b'%PDF-'):
                    raise ValueError(f'Expected PDF at {url}')
                if not pdf:
                    response.encoding = 'utf-8'
                source = {'url': url, 'response_url': response.url,
                          'http_status': response.status_code,
                          'sha256': hashlib.sha256(response.content).hexdigest()}
                if capture_dir:
                    name = f'source-{len(sources):02d}' + ('.pdf' if pdf else '.html')
                    (capture_dir / name).write_bytes(response.content)
                    source['capture'] = name
                sources.append(source)
                return response.text

            rows = self.parse_inventory(fetch(self.SOURCE))
            for row in rows:
                if '.pdf' in urlsplit(row['url']).path.lower():
                    fetch(row['url'], pdf=True)
                    row['documentos'] = [{
                        'titulo': row['titulo'], 'url': row['url'],
                        'href_publicado': row['href_inventario'],
                        'source_url': self.SOURCE, 'access_status': 'verified_pdf',
                    }]
                else:
                    row['documentos'] = self.parse_documents(fetch(row['url']), row['url'])
        result = self._write(out_jsonl, rows)
        result.update(source_urls=[s['url'] for s in sources], limitations=self.LIMITATIONS)
        if capture_dir:
            (capture_dir / 'sources.json').write_text(
                json.dumps(sources, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return result

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        result = self._write(out_jsonl, [])
        return {**result, 'status': 'disabled',
                'reason': 'No verified granted-licence register; application forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
