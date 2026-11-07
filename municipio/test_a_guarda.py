"""Offline parser regressions; live captures remain local evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.a_guarda import (
    AGuardaAyuntamientoAdapter, BASE, URBANISMO, discover, parse_inventories,
)
from municipio.manifest import load_manifest

SERVICE = '''<div class="entry-content"><p>O Concello de A Guarda conta cun
Plan Xeral de Ordenación Urbana vixente con aprobación definitiva do 29.07.93.</p></div>
<a href="/servizos-municipais/urbanismo/ordenanzas/">Ordenanzas</a>
<a href="/servizos-municipais/urbanismo/planos/">Planos</a>'''
ORDINANCES = '''<div class="entry-content">
<a href="/documents/general.pdf">Plan xeral de ordenación urbana (1993)</a>
<a href="/documents/general.pdf">Plan xeral de ordenación urbana (1993)</a>
<a href="/documents/mod.pdf">Modificación Nº1 do P.X.O.U. (1997)</a>
<a href="/documents/form.pdf">Solicitude licenza de obra nova</a></div>'''
MAPS = '''<div class="entry-content">
<a href="/maps/referencia.jpg">Índice</a><a href="/maps/2.1.jpg">[2.1]</a>
<a href="/maps/2.1.jpg">[2.1]</a><a href="http://www.planeamentourbanistico.xunta.es/">Visor</a>
</div>'''


class AGuardaTests(unittest.TestCase):
    def parse(self, service=SERVICE, ordinances=ORDINANCES, maps=MAPS):
        return parse_inventories(service, ordinances, maps, discover(service))

    def test_grouping_and_date_semantics(self):
        rows = self.parse()
        self.assertEqual(len(rows), 2)
        plan, modification = rows
        self.assertEqual(len(plan['documentos']), 3)
        self.assertEqual(len(modification['documentos']), 1)
        self.assertEqual(plan['fecha_aprob'], '1993-07-29')
        self.assertEqual(plan['fecha_aprob_source_url'], URBANISMO)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '36023')
            self.assertNotIn('fecha_publicacion', row)
            self.assertNotIn('fecha', row)
            self.assertNotIn('lat', row)
            self.assertTrue(all(d['source_url'].startswith(BASE) for d in row['documentos']))
        self.assertNotIn('fecha_aprob', modification)
        reordered = ORDINANCES.replace('general.pdf', 'renamed.pdf')
        self.assertEqual(self.parse(ordinances=reordered)[1]['id'], modification['id'])

    def test_source_drift_fails(self):
        for kwargs in [
            {'service': SERVICE.replace('29.07.93', 'data descoñecida')},
            {'ordinances': '<div class="entry-content">Formularios</div>'},
            {'maps': '<div class="entry-content">Sen planos</div>'},
            {'ordinances': ORDINANCES + '<a rel="next" href="/page/2/">2</a>'},
            {'maps': MAPS + '<a href="?paged=2">2</a>'},
            {'ordinances': ORDINANCES.replace('/documents/mod.pdf', 'https://example.org/mod.pdf')},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.parse(**kwargs)
        with self.assertRaises(ValueError):
            discover('<html>Missing navigation</html>')

    def test_disabled_licences_do_not_fetch(self):
        adapter = AGuardaAyuntamientoAdapter('a-guarda')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch') as fetch:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')
            fetch.assert_not_called()

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('a-guarda')
        self.assertEqual(manifest.nombre, 'A Guarda')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter,
                         'municipio.adapters.a_guarda:AGuardaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
