import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_maria_de_cayon import (
    SantaMariaDeCayonAyuntamientoAdapter as Adapter, pdf_dates,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


INVENTORY = '''<div class="item-page"><div itemprop="articleBody">
<p><a href="/normas.pdf">Normas Subsidarias de 1987</a></p>
<p><a href="/mod.pdf">Aprobación definitiva de modificación de Normas Subsidiarias. Expediente 2013/16</a></p>
<ul><li><a href="http://boc.cantabria.es/boces/verBoletin.do?idBolOrd=1">Boletín</a></li></ul>
<p><a href="/correction.pdf">Corrección de errores. Expediente 2013/16</a></p>
<p>Modificación Puntual en suelo productivo</p>
<p>Aprobación definitiva de Modificación Puntual de Normas Subsidiarias. Expediente 2021/746</p>
<ul><li><a href="https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=2">Documento BOC</a></li></ul>
</div></div>'''


class PlanningTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_dates(self):
        rows = Adapter.parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 3, 1])
        self.assertEqual(rows[1]['documentos'][2]['tipo'], 'correccion')
        self.assertEqual(rows[2]['expediente'], '2021/746')
        self.assertTrue(rows[1]['documentos'][1]['url'].startswith('https://boc.'))
        for row in rows:
            self.assertNotIn('fecha_aprob', row)
            self.assertNotIn('fecha', row)
            self.assertNotIn('lat', row)

    def test_duplicate_documents(self):
        duplicate = INVENTORY.replace('</div></div>', '<p><a href="https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=2">Repetido</a></p></div></div>')
        self.assertEqual(len(Adapter.parse_inventory(duplicate)[2]['documentos']), 1)

    def test_fail_closed_on_changed_inventory_or_pagination(self):
        for html in ['<h1>Error</h1>', INVENTORY + '<div class="pagination"><a href="?start=10">2</a></div>',
                     INVENTORY + '<a rel="next" href="?start=10">Más</a>',
                     INVENTORY.replace('<p>Modificación Puntual en suelo productivo</p>', '<p>Modificación Puntual nueva</p><p><a href="/new.pdf">Nuevo documento</a></p>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_explicit_dates_distinct_from_signature_and_document_date(self):
        dates = pdf_dates('LUNES, 14 DE ABRIL DE 2025 - BOC NÚM. 72\nEl Pleno en sesión ordinaria celebrada el día\n31 de enero de 2025, acordó la aprobación definitiva.\nSanta María de Cayón, 13 de marzo de 2025.\fOctubre 2024')
        self.assertEqual(dates, {'fecha_publicacion': '2025-04-14', 'fecha_acuerdo': '2025-01-31'})
        self.assertEqual(pdf_dates('Santa María de Cayón, 23 de enero de 1987'), {})

    def test_disabled_licences_and_manifest_loading(self):
        manifest = load_manifest('santa-maria-de-cayon')
        self.assertEqual(manifest.provincia, 'Cantabria')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', side_effect=AssertionError('No network for licences')):
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
