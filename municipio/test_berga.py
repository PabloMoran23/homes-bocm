import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.berga import BergaAyuntamientoAdapter, LANDING, SOURCE, parse_projects
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


# Small representative archive, intentionally independent of live network access.
ARCHIVE = """<html><body><b>POUM<br>PLA D'ORDENACIÓ URBANÍSTICA MUNICIPAL DE BERGA</b>
<a href="altres/dogc.pdf">APROVACI&Oacute; DEFINITIVA<br>DOGC 4341 - 11/03/2005</a>
<a href="memoria/memoria.pdf">Memòria</a>
<a href="fitxes/pmu.pdf">Plans de Millora Urbana</a>
<a href="normes/normes.pdf">Normes urbanístiques</a>
<table><tr><td>1.- Estructura general</td><td><a href="planols/01.pdf">195 Kb</a></td></tr></table>
</body></html>"""


class BergaParserTests(unittest.TestCase):
    def test_groups_components_and_preserves_provenance(self):
        rows = parse_projects(ARCHIVE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '08022')
        self.assertEqual(len(row['documentos']), 5)
        doc = row['documentos'][-1]
        self.assertEqual(doc['url'], SOURCE.rsplit('/', 1)[0] + '/planols/01.pdf')
        self.assertIn('Estructura general', doc['contexto_fuente'])
        self.assertEqual(doc['inventory_url'], SOURCE)
        self.assertIsNone(row['geometry'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])

    def test_publication_is_not_approval_or_agreement(self):
        row = parse_projects(ARCHIVE)[0]
        self.assertEqual(row['fecha_publicacion'], '2005-03-11')
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob'):
            self.assertIsNone(row[key])
        self.assertIsNone(parse_projects(ARCHIVE.replace(' - 11/03/2005', ''))[0]['fecha_publicacion'])

    def test_legacy_multiline_labels(self):
        html = ARCHIVE.replace('DEFINITIVA', '\r\n       DEFINITIVA').replace('DOGC 4341', 'DOGC\r\n  4341')
        self.assertEqual(parse_projects(html)[0]['fecha_publicacion'], '2005-03-11')

    def test_duplicate_links_are_not_duplicate_instruments(self):
        duplicate = ARCHIVE + '<a href="normes/normes.pdf">Normes</a>'
        self.assertEqual(len(parse_projects(duplicate)[0]['documentos']), 5)
        self.assertEqual(parse_projects(duplicate)[0]['id'], parse_projects(ARCHIVE)[0]['id'])

    def test_forms_news_and_navigation_are_not_plans(self):
        for html in ('<a href="poum">POUM</a>', '<h1>Tràmit de llicència</h1>',
                     '<h1>Berga licita obres</h1>', '<form>Login</form>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_incomplete_or_conflicting_inventory_fails(self):
        for html in (ARCHIVE.replace('planols/01.pdf', 'altres/01.pdf'),
                     ARCHIVE.replace('APROVACI&Oacute; DEFINITIVA', 'Avís'),
                     ARCHIVE + '<a href="altres/other.pdf">APROVACIÓ DEFINITIVA DOGC 9999 - 12/03/2005</a>',
                     ARCHIVE.replace('11/03/2005', '31/02/2005')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_continuation_or_external_document_is_never_silently_dropped(self):
        for extra in ('<a rel="next" href="?page=2">Següent</a>',
                      '<a href="page2.htm">2</a>', '<iframe src="documents"></iframe>',
                      '<a href="https://example.org/doc.pdf">Document</a>',
                      '<a href="../../outside.pdf">Document</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_projects(ARCHIVE + extra)

    def test_backfill_and_update_write_same_complete_snapshot(self):
        adapter = BergaAyuntamientoAdapter('berga')
        landing = f'<a href="{SOURCE}">POUM</a>'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[(landing, {}), (ARCHIVE, {})] * 2):
                result = adapter.backfill_proyectos(output)
                first = output.read_text()
                adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(first, output.read_text())
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(json.loads(first)['documentos']), 5)
            self.assertFalse((Path(directory) / 'state.json').exists())

    def test_changed_landing_fails_before_output(self):
        adapter = BergaAyuntamientoAdapter('berga')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', return_value=('<h1>Login</h1>', {})):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertFalse(output.exists())

    def test_manifest_loads_and_disables_licences(self):
        manifest = load_manifest('berga')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08022')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, BergaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
