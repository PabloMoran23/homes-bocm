"""Offline parser and crawl failure tests; no network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.begues import (
    SOURCE, BeguesAyuntamientoAdapter, amendment_number, agreement_date,
    group_amendments, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(page=1, total=2, title='Modificació PGO 31', slug='pgo-31'):
    href = SOURCE + (f'?pag={page}' if page > 1 else '')
    return f'''<div id="readspeakerPage"><h1>Projectes urbanístics</h1>
    <ul class="paginacio"><a aria-current="page" href="{href}">{page}</a>
    <a class="info">{total} pàgines</a></ul>
    <ul class="articlelist"><li class="article-item"><div class="tplDefault">
    <a href="{SOURCE}{slug}.html">{title}</a><div class="date">19/08/2026</div>
    </div></li></ul></div>'''


def detail(text='Aprovat inicialment pel Ple de data 20 de juliol de 2026', number=31):
    return f'''<div id="readspeakerPage"><h1>Modificació PGO {number}</h1>
    <div class="ddbbtext">{text}</div><span class="updated">2.11.2026</span></div>
    <section id="page-documents"><a href="/media/repository/plan.pdf">Pla</a>
    <a href="/media/repository/normes.pdf">Normes</a></section>'''


class BeguesTests(unittest.TestCase):
    def test_numbers_and_exclusions(self):
        for title in ["MODIFICACIÓ PUNTUAL DEL PLA GENERAL D'ORDENACIÓ NÚM. 35", 'Modificació de PGOU núm. 35.']:
            self.assertEqual(amendment_number(title), 35)
        for title in ['Conveni urbanístic pel desenvolupament de la Modificació de PGO 27',
                      'PROJECTE URBANITZACIÓ UNITAT ACTUACIÓ 11', 'Sol·licitud llicència obres',
                      'PLA DIRECTOR URBANÍSTIC METROPOLITÀ']:
            self.assertIsNone(amendment_number(title))

    def test_dates_and_documents(self):
        _, entries, _ = parse_inventory(inventory())
        event = parse_detail(detail(), entries[0])
        self.assertEqual(event['fecha_publicacion'], '2026-08-19')
        self.assertEqual(event['fecha_acuerdo'], '2026-07-20')
        self.assertEqual(event['fase'], 'aprobación inicial')
        self.assertEqual(len(event['documentos']), 2)
        self.assertEqual(event['documentos'][0]['source_url'], entries[0]['url'])
        self.assertEqual(agreement_date("Aprovada provisionalment pel Ple de 2 d’octubre de 2023."), '2023-10-02')
        self.assertEqual(agreement_date('Aprovat pel Ple de 21/12/2021'), '2021-12-21')
        self.assertIsNone(agreement_date('Publicat el 21/12/2021. Darrera actualització: 2.11.2026'))
        self.assertIsNone(agreement_date('Aprovat pel Ple de 21/12/2021 i 22/12/2021'))

    def test_grouping_retains_stages_and_document_provenance(self):
        _, entries, _ = parse_inventory(inventory())
        old = parse_detail(detail(), entries[0])
        old.update(fecha_publicacion='2023-03-01', url=SOURCE + 'older.html')
        newer = parse_detail(detail('Aprovat provisionalment pel Ple de 2/10/2023'), entries[0])
        rows = group_amendments([old, newer])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'begues-proy-pgo-31')
        self.assertEqual(len(rows[0]['publicaciones']), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[0]['documentos'][0]['source_urls']), 2)
        self.assertIsNone(rows[0]['lat'])
        self.assertIsNone(rows[0]['fecha'])

    def test_fail_closed_on_markup_wrong_instrument_and_pagination(self):
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Login</h1>')
        with self.assertRaises(ValueError):
            parse_inventory(inventory(), SOURCE + '?pag=2')
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('2 pàgines', '201 pàgines'))
        _, entries, _ = parse_inventory(inventory())
        with self.assertRaises(ValueError):
            parse_detail(detail(number=34), entries[0])
        with self.assertRaises(ValueError):
            parse_detail('<div id="readspeakerPage"><h1>Modificació PGO 31</h1></div>', entries[0])

    def test_full_pagination_and_no_partial_write(self):
        adapter = BeguesAyuntamientoAdapter('begues')
        pages = {SOURCE: inventory(), SOURCE + '?pag=2': inventory(2, title='Modificació PGO 35', slug='pgo-35'),
                 SOURCE + 'pgo-31.html': detail(), SOURCE + 'pgo-35.html': detail(number=35)}
        def fetch(url):
            adapter.source_urls.append(url)
            return pages[url]
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(folder) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 2)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len(out.read_text().splitlines()), 2)
            previous = out.read_bytes()
            pages[SOURCE + '?pag=2'] = inventory()
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)

    def test_manifest(self):
        manifest = load_manifest('begues')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Begues', 'Barcelona', '08020'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
