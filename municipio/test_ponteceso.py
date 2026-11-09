"""Offline semantic and failure-path tests; no live HTTP in unit tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.ponteceso import (
    SOURCE, PontecesoAyuntamientoAdapter, enrich_base_plan, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

INVENTORY = '''<html><head><title>PXOM de Ponteceso</title></head><body>
<p>Plan Xeral de Ordenación Municipal</p>
<p>Aprobación definitiva no Pleno Municipal do luns, 9 de Marzo de 2015.</p>
<a href="http://www.xunta.es/dog/Publicados/2015/20150522/AnuncioCA02-190515-0005_gl.html">D.O.G.</a>
<a href="PXOM2015/NORMATIVA.pdf">Normativa Urbanística</a>
<map><area href="PXOM2015/Plano A.pdf"></map>
<a href="PXOM2015/Plano%20A.pdf">Duplicated map link</a>
<a href="PXOM/DOG290319NORMATIVA.PDF">Modificación MR-Lestimoño DOG 29/03/19</a>
<a href="PXOM/memoria.pdf">Memoria modificación MR-Lestimoño</a>
<a href="pxom2002.html">Antigo PXOM</a>
<a href="/licenza">Solicitude licenza</a>
</body></html>'''
DOG = '''<html><title>DOG 95 do 22/05/2015 - ORDE do 6 de maio de 2015 de aprobación definitiva do Plan xeral de ordenación municipal de Ponteceso.</title></html>'''


class PontecesoTests(unittest.TestCase):
    def test_group_documents_and_image_maps(self):
        rows, dog = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertTrue(rows[0]['documentos'][1]['url'].endswith('Plano%20A.pdf'))
        self.assertEqual(rows[1]['fecha_publicacion'], '2019-03-29')
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertTrue(dog.startswith('https://www.xunta.gal/'))
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['geometry'])

    def test_authoritative_order_date_not_municipal_claim(self):
        rows, dog = parse_inventory(INVENTORY)
        enrich_base_plan(rows[0], DOG, dog)
        self.assertEqual(rows[0]['fecha_aprob'], '2015-05-06')
        self.assertEqual(rows[0]['fecha_publicacion'], '2015-05-22')
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertIsNone(rows[0]['fecha'])
        self.assertEqual(rows[0]['fecha_aprob_fuente'], dog)
        with self.assertRaises(ValueError):
            enrich_base_plan(rows[0], DOG.replace('Ponteceso.', 'Otro.'), dog)

    def test_pagination_rejected(self):
        for control in ['<a href="p2" rel="next">2</a>', '<a href="p2">Seguinte</a>',
                        '<div class="pagination"><a href="p2">2</a></div>']:
            with self.subTest(control=control), self.assertRaises(ValueError):
                parse_inventory(INVENTORY.replace('</body>', control + '</body>'))

    def test_missing_or_new_instrument_fails(self):
        for html in ['Please wait while verified', INVENTORY.replace('NORMATIVA.pdf', 'unclassified.pdf'),
                     INVENTORY.replace('</body>', '<a href="PXOM/another.pdf">New plan</a></body>'),
                     INVENTORY.replace('DOG 29/03/19', 'DOG')]:
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_refresh_atomic_and_licences_disabled(self):
        adapter = PontecesoAyuntamientoAdapter('ponteceso')
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, DOG]):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 2)
            before = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, '<title>Challenge</title>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)
            self.assertEqual(json.loads(out.read_text().splitlines()[0])['codigo_ine'], '15068')
            with patch.object(adapter, '_fetch', side_effect=AssertionError('No licence HTTP allowed')):
                result = adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')

    def test_manifest_and_adapter_contract(self):
        manifest = load_manifest('ponteceso')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '15068')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), PontecesoAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
