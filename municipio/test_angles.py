import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.angles import AnglesAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

TITLE = 'Reforma dels lavabos del CEIP Pompeu Fabra'
URL = 'https://som.angles.cat/projecte/lavabos'
ENTRY = {'node_id': 'node-1489', 'titulo': TITLE, 'url': URL, 'included': True}


def inventory(node='1489', title=TITLE, path='/projecte/lavabos', pager=''):
    return f'<div class="view-content"><article class="node-projecte" id="node-{node}"><h2><a href="{path}">{title}</a></h2></article></div>{pager}'


def detail(node='1489', title=TITLE, start='24/09/2018', end='11/01/2019'):
    return f'''<div id="main-content"><h1 class="page-title">{title}</h1>
    <article class="node-projecte" id="node-{node}">
    <div class="submitted">Publicat per admin el dv., 28/06/2019 - 19:48</div>
    <div class="field-name-field-projecte-inici"><span class="date-display-single">{start}</span></div>
    <div class="field-name-field-projecte-fi"><span class="date-display-single">{end}</span></div>
    <div class="field-name-body"><div class="field-items"><p>S'han dut a terme les obres de reforma.</p>
    <a href="/sites/default/files/projecte.pdf">Projecte</a>
    <a href="/sites/default/files/projecte.pdf">Duplicat</a>
    <a href="https://angles.emunicipis.ddgi.cat/OAC/download/abc">Conveni</a>
    <a href="https://contractaciopublica.gencat.cat/award">Contractació</a></div></div>
    </article></div>'''


class AnglesTests(unittest.TestCase):
    def test_dates_and_grouped_document_provenance(self):
        row = Adapter.parse_project(detail(), ENTRY)
        self.assertEqual(row['fecha_publicacion'], '2019-06-28')
        self.assertEqual(row['fecha_inicio'], '2018-09-24')
        self.assertEqual(row['fecha_fin'], '2019-01-11')
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['enlaces_relacionados']), 3)
        self.assertTrue(all(d['source_url'] == URL and not d['content_verified'] for d in row['documentos']))

    def test_date_anomaly_is_preserved(self):
        row = Adapter.parse_project(detail(start='20/11/2017', end='15/12/2016'), ENTRY)
        self.assertEqual(row['fecha_inicio'], '2017-11-20')
        self.assertEqual(row['fecha_fin'], '2016-12-15')
        self.assertTrue(row['quality_warnings'])
        missing = Adapter.parse_project(detail(start='', end='').replace('28/06/2019', ''), ENTRY)
        self.assertIsNone(missing['fecha_publicacion'])
        self.assertIsNone(missing['fecha_inicio'])

    def test_exclusions_and_unknown_categories(self):
        entries, _ = Adapter.parse_inventory(inventory('120', 'Projecte d´Acció Social i Inserció Laboral'))
        self.assertFalse(entries[0]['included'])
        entries, _ = Adapter.parse_inventory(inventory('122', 'Polítiques d´habitatge adreçades a fomentar la rehabilitació'))
        self.assertFalse(entries[0]['included'])
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            Adapter.parse_inventory(inventory(title='Sol·licitud de llicència'))

    def test_reject_navigation_wrong_detail_and_nonwork(self):
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<a href="/projecte/lavabos">Projectes</a>')
        with self.assertRaises(ValueError):
            Adapter.parse_project(detail(node='123'), ENTRY)
        with self.assertRaises(ValueError):
            Adapter.parse_project(detail().replace("S'han dut a terme les obres de reforma.", 'Formulari de sol·licitud'), ENTRY)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory(path='https://example.org/projecte/fake'))

    def test_full_pagination_deduplication_and_update(self):
        page2 = SOURCE + '?page=1'
        page1 = inventory(pager='<ul class="pager"><a href="?page=1">2</a></ul>')
        second = inventory('1490', 'Rehabilitació dels habitatges del carrer Fàbriques', '/projecte/fabriques',
                           f'<ul class="pager"><a href="{SOURCE}">1</a></ul>')
        pages = {SOURCE: page1, page2: second, URL: detail(),
                 'https://som.angles.cat/projecte/fabriques': detail('1490', 'Rehabilitació dels habitatges del carrer Fàbriques')}
        adapter = Adapter('angles')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)
            self.assertEqual(fetch.call_count, 4)
            self.assertIn(page2, result['source_urls'])

    def test_failed_page_leaves_existing_snapshot_intact(self):
        adapter = Adapter('angles')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[inventory(pager='<a rel="next" href="?page=1">Next</a>'), '<html>Unavailable</html>']):
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_adapter_loads_and_licences_disabled(self):
        manifest = load_manifest('angles')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Girona')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
