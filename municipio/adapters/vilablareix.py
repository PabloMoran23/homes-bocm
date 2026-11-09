"""Municipal technical-document collection, grouped into reviewed instruments.

This collection contains historical versions; presence does not establish that a
plan is currently in force. The separate electronic notice board is out of scope.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.vilablareix.cat/taxonomy/term/22'
# Associations reviewed against the municipal PDF memories, not inferred from
# adjacency in the inventory. Both Marroc II memories describe the same UA.
GROUPS = {
    'nnss-industrials-16': (
        'Modificació puntual de Normes Subsidiàries — Sectors industrials (16)',
        '2013_Mod_NNSS_c16.pdf',
        ['2013_Mod_NNSS_c16.pdf']),
    'perello-can-pere-martir': (
        'Modificació puntual del Pla parcial urbanístic — El Perelló i Can Pere Màrtir',
        'Memoria_PP_2.pdf',
        ['09PAR-MOD2-AP.pdf', '090528_MPElPerello_NUcat.pdf', '06-07ZONIF-MOD2-AP.pdf',
         '06-07ZONIF.pdf', 'Memoria_PP_2.pdf', '10OP.pdf', '09PAR.pdf', '01EMPL.pdf']),
    'perusnu': (
        'Pla especial de regulació dels usos del sòl no urbanitzable de Vilablareix',
        'PERUSNU_Vilablareix.pdf',
        ['APROVACIO_INICIAL_BOP.pdf', 'ORDENACIO_Vilablareix.pdf', 'PERUSNU_Vilablareix.pdf',
         '6_Vialitat_Vilablareix.pdf', '5_Riscos_Vilablareix.pdf', '4_EINs_Vilablareix.pdf',
         '3_Planejament_Vilablareix.pdf', '2_MC_Vilablareix.pdf', '1_Habitats_Vilablareix.pdf']),
    'nnss-marroc-ii': (
        'Modificació puntual de les Normes Subsidiàries — U.A. Marroc II',
        'UA3_Memoria.pdf',
        ['UA3_USOS_GLOB_05.pdf', 'UA3_TOPOG_00.pdf', 'UA3_Qual__sol_urba_04.pdf',
         'UA3_Alin_sol_urb_06.pdf', 'UA3_Memoria.pdf', 'CONVENI_definitiu_Marroc_II.pdf',
         '05-11_PARCEL.LACIO.pdf', 'P-06_Alineacions_sol_urba.pdf', 'P-05_USOS_GLOBALS.pdf',
         'P-04_Qualificacio_sol_urba.pdf', 'P-00_TOPOGRAFIC.pdf',
         'MEMORIA_MODIFICACIO_PUNTUAL_DE_LES_NORMES_SUBSIDIARIES.pdf']),
}


class VilablareixAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.vilablareix.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main')
        if main is None:
            raise ValueError('Municipal document inventory missing')
        # Never accept an unvisited page of an inventory. A changed pagination
        # mechanism requires review rather than silently returning a subset.
        if main.select('.pager, .pagination, [rel="next"], [rel="last"]') or any(
            'page=' in a['href'] or '__doPostBack' in a['href']
            for a in main.select('a[href]')
        ):
            raise ValueError('Inventory is paginated; crawler requires review')
        expected = {name for _, _, names in GROUPS.values() for name in names}
        documents = {}
        for block in main.select('.views-row .content-tax'):
            title = block.select_one('.content-title-tax')
            links = block.select('.content-enllacos-tax a[href]')
            if title is None or not links:
                raise ValueError('Unrecognized document row')
            for a in links:
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                name = unquote(parsed.path.rsplit('/', 1)[-1])
                if (parsed.scheme != 'https' or parsed.netloc != 'www.vilablareix.cat'
                        or not parsed.path.startswith('/sites/default/files/')
                        or parsed.query or parsed.fragment or name not in expected):
                    raise ValueError(f'Unreviewed inventory document: {url}')
                documents.setdefault(name, {
                    'titulo': title.get_text(' ', strip=True), 'url': url,
                    'source_url': SOURCE,
                })
        if set(documents) != expected:
            raise ValueError('Inventory is empty or reviewed documents are missing')
        rows = []
        for key, (title, primary, names) in GROUPS.items():
            rows.append({
                'id': 'vilablareix-proy-' + key,
                'municipio': 'Vilablareix', 'codigo_ine': '17215', 'provincia': 'Girona',
                'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'url': SOURCE,
                'url_documento': documents[primary]['url'],
                'documentos': [documents[n] for n in names],
                'source': 'ayuntamiento', 'origen': 'coleccion_documental_planejament',
                'descripcion': 'Instrumento documentado en la colección municipal. Se agrupan '
                    'memorias, planos y anexos, incluidas versiones históricas. La presencia '
                    'en esta colección no acredita vigencia ni aprobación actual.',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Colección documental parcial; no incluye el tauler ni todo el RPUC.',
            })
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-vilablareix/1.0')})
        with response:
            response.raise_for_status()
            if urlparse(response.url).netloc != 'www.vilablareix.cat':
                raise ValueError('Inventory redirected outside municipality')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 2_000_000:
                    raise ValueError('Inventory exceeds reviewed size limit')
            html = bytes(content).decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            Path(capture_dir).mkdir(parents=True, exist_ok=True)
            Path(capture_dir, 'inventory.html').write_text(html, encoding='utf-8')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        # Disabled sources do not overwrite existing licence output.
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
