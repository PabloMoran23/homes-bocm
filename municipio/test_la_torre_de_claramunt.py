"""Offline contract tests; no source captures or network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_torre_de_claramunt import (
    LaTorreDeClaramuntAyuntamientoAdapter as Adapter, INVENTORY, PLANNING,
)
from municipio.manifest import load_manifest, load_yaml

TITLE = 'EXPOSICIÓ PÚBLICA RENOVACIÓ DE LA XARXA DE LA FONT DEL CAMARÓ 1era FASE'
URL = INVENTORY + '/exposicio-publica-renovacio-226'
PLAN = '''<main><div id="readspeakerPage"><div class="subtitle">NN SS Planejament Urbanístic del municipi de La Torre de Claramunt</div>
<div class="ddbbtext">NNSS vigents i aprovades per la Comissió d'Urbanisme de Barcelona en sessió 15-10-1986.
Text Refós amb les modificacions.</div><span class="updated">Darrera actualització: 30.11.2020 | 08:53</span></div>
<section id="page-documents"><a href="/media/repository/nnss.pdf">NNSS</a><a href="/media/repository/nnss.pdf">NNSS duplicate</a></section></main>'''
INDEX = f'''<main><a href="{URL}">{TITLE}</a><a href="{URL}">{TITLE}</a>
<a href="{INVENTORY}/proteccio-civil">PROTECCIÓ CIVIL MUNICIPAL. DUPROCIM</a>
<a href="/tramits/licencia">Sol·licitud de llicència</a></main>'''
WORK = f'''<main><h1 class="page-title">{TITLE}</h1><div class="journal-content-article">
<a href="/documents/1946839/1/certificat/uuid1">CERTIFICAT DE SECRETARIA. APROVACIÓ MEMÒRIA VALORADA</a>
<a href="/documents/1946839/1/memoria/uuid2">MEMÒRIA VALORADA PER A LA RENOVACIÓ DE XARXA</a>
<a href="/documents/1946839/1/memoria/uuid2">MEMÒRIA VALORADA duplicate</a>
<div class="datatable_info_footer paginacio_footer">Actualització: 07/07/2026 | Font: Propi ens</div></div></main>'''


class Tests(unittest.TestCase):
    def test_plan_approval_not_page_update(self):
        row = Adapter.parse_planning(PLAN)
        self.assertEqual(row['fecha_aprob'], '1986-10-15')
        self.assertEqual(row['fecha_actualizacion_fuente'], '2020-11-30')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(len(row['documentos']), 1)
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])

    def test_inventory_deduplicates_and_excludes_forms_civil_protection(self):
        self.assertEqual(Adapter.parse_inventory(INDEX), {URL: TITLE})

    def test_work_groups_documents_without_inventing_dates(self):
        row = Adapter.parse_work(WORK, URL, TITLE)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_actualizacion_fuente'], '2026-07-07')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['fase'], 'exposición pública')
        self.assertTrue(all(d['source_url'] == URL for d in row['documentos']))

    def test_pagination_fails_instead_of_truncating(self):
        for extra in ['<a href="?page=2" rel="next">2</a>', '<a href="?page=2">Següent</a>',
                      '<ul class="pagination"><li><a href="?page=2">2</a></li></ul>']:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(INDEX.replace('</main>', extra + '</main>'))

    def test_changed_and_empty_sources_fail(self):
        for html in ['<main>No data</main>', '<html>Login</html>', PLAN.replace('15-10-1986', 'unknown'),
                     PLAN.replace('/media/repository/nnss.pdf', '/form')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_planning(html)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<main>No projects</main>')

    def test_certificate_or_procurement_alone_is_insufficient(self):
        html = WORK.replace('MEMÒRIA VALORADA PER A LA RENOVACIÓ DE XARXA', 'ANUNCI LICITACIÓ').replace('MEMÒRIA VALORADA duplicate', 'LICITACIÓ')
        with self.assertRaises(ValueError):
            Adapter.parse_work(html, URL, TITLE)
        with self.assertRaises(ValueError):
            Adapter.parse_work(WORK.replace('class="page-title"', 'class="other"'), URL, TITLE)

    def test_snapshot_updates_and_failed_fetch_preserves_output(self):
        adapter = Adapter('la-torre-de-claramunt')
        sources = {PLANNING: PLAN, INVENTORY: INDEX, URL: WORK}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            state = Path(directory) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
                result = adapter.backfill_proyectos(out)
                self.assertEqual(result['rows'], 2)
                original = out.read_text()
                adapter.update_proyectos(out, state)
                self.assertEqual(out.read_text(), original)
                self.assertEqual(len({r['id'] for r in map(json.loads, original.splitlines())}), 2)
            with patch.object(adapter, '_fetch', side_effect=ValueError('offline')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), original)
            lic = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('la-torre-de-claramunt')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08286')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
