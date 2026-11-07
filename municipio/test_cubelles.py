import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cubelles import (
    SOURCE, CubellesAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest

TITLE = "Projecte d'urbanització de l'antiga central tèrmica de Cubelles"
URL = SOURCE + '/central.html'


def inventory(url=URL, pager='', date='28/10/2025'):
    return f'''<div id="readspeakerPage"><h1>Projectes</h1>
    <ul class="articlelist"><li class="article-item"><a href="{url}">{TITLE}</a>
    <div class="date">{date}</div></li></ul><div class="pager">{pager}</div></div>'''


def detail(technical=True):
    doc = '<a href="/media/projecte.pdf"><span class="txt">Projecte <span class="file-size">(10MB)</span><span class="author">Ajuntament de Cubelles</span></span></a>' if technical else ''
    return f'''<div id="readspeakerPage"><div class="containerArticle"><h1>{TITLE}</h1>
    <div class="date">Dimarts, 28 d’octubre de 2025</div>
    <div class="ddbbtext">Informació pública de l'aprovació inicial del Projecte d'urbanització</div>
    <span class="updated">Darrera actualització: 14.09.2026</span></div></div>
    <section id="page-documents"><div class="documents">{doc}{doc}
    <a href="/media/anunci.pdf"><span class="txt">Anunci BOPB</span></a></div></section>'''


class CubellesTests(unittest.TestCase):
    def test_grouped_documents_and_date_semantics(self):
        entries, pages = parse_inventory(inventory())
        record = parse_project(detail(), entries[0])
        self.assertEqual(pages, [])
        self.assertEqual(record['fecha_publicacion'], '2025-10-28')
        self.assertEqual(record['fase'], 'aprobación inicial')
        self.assertIsNone(record['fecha_aprob'])
        self.assertIsNone(record['fecha_acuerdo'])
        self.assertEqual(len(record['documentos']), 2)
        self.assertEqual(record['documentos'][0]['titulo'], 'Projecte')
        self.assertEqual(record['documentos'][0]['publisher'], 'Ajuntament de Cubelles')
        self.assertIsNone(record['geometry'])
        self.assertFalse(record['publication_ready'])

    def test_no_inferred_phase_or_dates(self):
        entry = parse_inventory(inventory(date=''))[0][0]
        record = parse_project(detail().replace("Informació pública de l'aprovació inicial del Projecte d'urbanització", ''), entry)
        self.assertIsNone(record['fase'])
        self.assertIsNone(record['fecha_publicacion'])

    def test_reject_forms_news_and_notice_only(self):
        for html in ('<h1>Login</h1>', inventory().replace(TITLE, 'Sol·licitud de llicència'),
                     inventory().replace(TITLE, 'Anunci de licitació')):
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_project(detail(False), parse_inventory(inventory())[0][0])
        with self.assertRaises(ValueError):
            parse_project(detail().replace(TITLE, 'Other project'), parse_inventory(inventory())[0][0])

    def test_all_pagination_and_duplicate_instrument(self):
        page2 = SOURCE + '?page=2'
        adapter = CubellesAyuntamientoAdapter()
        captures = {SOURCE: inventory(pager=f'<a rel="next" href="{page2}">2</a>'),
                    page2: inventory(pager=f'<a href="{SOURCE}">1</a>'), URL: detail()}
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda url: captures[url]) as fetch:
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '08074')

    def test_pagination_and_external_fail_closed(self):
        for pager in ('<a href="https://example.org/next">next</a>', '<button>Next</button>', '<a href="#next">Next</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(inventory(pager=pager))
        with self.assertRaises(ValueError):
            parse_project(detail().replace('/media/projecte.pdf', 'https://example.org/projecte.pdf'), parse_inventory(inventory())[0][0])

    def test_failure_does_not_write_partial_snapshot(self):
        adapter = CubellesAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=[inventory(), detail(False)]):
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous complete snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous complete snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cubelles')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertEqual(manifest.portal.config['ine_code'], '08074')
        self.assertEqual(CubellesAyuntamientoAdapter().backfill_licencias(Path('/unused'))['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
