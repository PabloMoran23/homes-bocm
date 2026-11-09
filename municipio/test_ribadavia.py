import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ribadavia import (
    RibadaviaAyuntamientoAdapter, SOURCE, STATUS_SOURCE, parse_inventory, parse_approval,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest

INVENTORY = '''<h1 class="entry-title">PXOM</h1><a href="/unrelated.pdf">Form</a>
<article><div class="entry">
<a href="http://www.planeamentourbanistico.xunta.es/siotuga/rexistro/index.php?url=RIBADAVIA_PXOM_TEST.zip">PLAN XERAL DE ORDENACIÓN MUNICIPAL</a>
<a href="/wp-content/uploads/2020/Normativa-Xestión.pdf">Normativa</a>
<a href="/wp-content/uploads/2020/Normativa-Xesti%C3%B3n.pdf">Duplicate</a>
<a href="/wp-content/uploads/2020/plano.pdf">Plano</a>
<a href="#tab">Tomo IV</a></div></article>'''
STATUS = '''<table><tr><td>32069</td><td>Ribadavia</td><td>Plan xeral de ordenación municipal</td><td>2019-11-29</td><td>Planeamento xeral adaptado á LOUG</td></tr></table>'''


class RibadaviaTests(unittest.TestCase):
    def test_grouping_dedup_and_scope(self):
        title, docs = parse_inventory(INVENTORY)
        self.assertIn('PLAN XERAL', title)
        self.assertEqual(len(docs), 3)
        self.assertIn('%C3%B3', docs[0]['url'])
        self.assertTrue(all(d['source_url'] == SOURCE for d in docs))
        self.assertFalse(any('unrelated' in d['url'] for d in docs))

    def test_fail_closed(self):
        for html in ('<html>Challenge</html>', INVENTORY.replace('RIBADAVIA_PXOM_', 'OTHER_'),
                     INVENTORY + '<a rel="next" href="/page/2/">Next</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)
        for html in (STATUS.replace('32069', '32068'), STATUS + STATUS,
                     STATUS.replace('2019-11-29', '2019-02-30'),
                     STATUS.replace('Ribadavia', 'Another town')):
            with self.assertRaises(ValueError):
                parse_approval(html)

    def test_refresh_dates_and_disabled_licences(self):
        manifest = load_manifest('ribadavia')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, RibadaviaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, STATUS, INVENTORY, STATUS]):
                adapter.backfill_proyectos(output)
                adapter.update_proyectos(output, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['fecha_aprob'], '2019-11-29')
            self.assertEqual(rows[0]['fecha_aprob_source_url'], STATUS_SOURCE)
            self.assertIsNone(rows[0]['fecha_publicacion'])
            self.assertIsNone(rows[0]['fecha_acuerdo'])
            self.assertIsNone(rows[0]['geometry'])
            self.assertEqual(len(rows[0]['documentos']), 3)
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
