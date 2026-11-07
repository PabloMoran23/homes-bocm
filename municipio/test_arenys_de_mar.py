"""Offline parser and snapshot integrity tests; no network calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arenys_de_mar import ArenysDeMarAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml

TITLE = "I.02. Modificació Puntual POUM correcció d'errada"
INVENTORY = f'''<h1>Planejament general</h1><ul><li class="fitxes">
<div class="titol"><a class="eltitol" href="fitxa.php?id=45275">{TITLE}</a></div>
<div class="sotstitol">Publicat al DOGC el 17/10/2023</div></li></ul>'''
DETAIL = f'''<div class="titol"><span class="eltitol">{TITLE}</span></div>
<div>Publicat al DOGC el 17/10/2023</div><div class="fitxes_bloc_cos">
<li class="fcamp119"><div class="cos_fitxa"><p>Aprovada definitivament el 12/12/2022 i donada conformitat el 21/07/2023.</p>
<a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/123">aquí</a></div></li>
<div class="div_pdf"><p class="descri_pdf">Text refós</p><a class="minipdf" href="ARXIUS/text.pdf">mini</a>
<a class="linkpdf" href="ARXIUS/text.pdf">text.pdf</a></div>
<div class="div_pdf"><a class="linkpdf" href="ARXIUS/mapa.pdf">mapa.pdf</a></div></div>'''


class ArenysDeMarTests(unittest.TestCase):
    def entry(self):
        return Adapter.parse_inventory(INVENTORY)[0]

    def test_grouping_dates_provenance_and_no_invented_location(self):
        row = Adapter.parse_detail(DETAIL, self.entry())
        self.assertEqual(row['fecha_publicacion'], '2023-10-17')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertIn('12/12/2022', row['descripcion'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], row['url'])
        self.assertEqual(row['documentos'][0]['url'], 'https://arenysdemar.cat/ARXIUS/text.pdf')
        self.assertEqual(row['rpuc_id'], '123')
        self.assertEqual(row['codigo_ine'], '08006')
        self.assertFalse(row['publication_ready'])
        for key in ('lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])

    def test_inventory_deduplicates_and_keeps_every_item(self):
        self.assertEqual(len(Adapter.parse_inventory(INVENTORY + INVENTORY)), 1)
        self.assertEqual(len(Adapter.parse_inventory(INVENTORY + INVENTORY.replace('45275', '46636'))), 2)

    def test_rejects_pagination(self):
        for extra in ('<a rel="next" href="?categoria=368&page=2">2</a>',
                      '<div class="paginacio"><a href="?pagina=2">2</a></div>',
                      '<a href="?inici=10">Següent</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_inventory(INVENTORY + extra)

    def test_rejects_wrong_inventory_forms_and_invalid_dates(self):
        for html in ('<p>login</p>', INVENTORY.replace(TITLE, 'Formulari llicència'),
                     INVENTORY.replace('17/10/2023', '31/02/2023'),
                     INVENTORY.replace('fitxa.php?id=45275', 'https://example.org/fitxa.php?id=45275')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_rejects_missing_documents_dossier_title_and_conflicting_dates(self):
        for html in (DETAIL.replace('linkpdf', 'other'), DETAIL.replace('dtes.gencat.cat', 'example.org'),
                     DETAIL.replace(TITLE, 'Unrelated news'), DETAIL.replace('17/10/2023', '18/10/2023')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_detail(html, self.entry())

    def test_failed_detail_does_not_overwrite_snapshot(self):
        adapter = Adapter('arenys-de-mar')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'proyectos.jsonl'
            target.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, '<p>login</p>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(target)
            self.assertEqual(target.read_text(), 'previous snapshot')
            adapter.backfill_licencias(target)
            self.assertEqual(target.read_text(), '')

    def test_manifest(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/arenys-de-mar/manifest.yaml'
        raw = load_yaml(path)
        manifest = load_manifest(path)
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertEqual(raw['codigo_ine'], '08006')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.arenys_de_mar:ArenysDeMarAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
