"""Offline parser tests; live source captures and output live under evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.curtis import CurtisAyuntamientoAdapter, SOURCE, parse_detail, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def article(title, body):
    return f'<article class="item"><h1>{title}</h1><div class="content clearfix">{body}</div></article>'


INVENTORY = article('PXOM', '''
<a href="/index.php/es/aviso/modificaciones">Planos de las modificaciones puntuales 6 y 7</a>
<a href="/index.php/es/aviso/ape">Proyecto de reparcelación APE-4</a>
<a href="/index.php/es/aviso/ape">Proyecto de reparcelación APE-4</a>
<a href="http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php">Plan General</a>
''')
MODIFICATIONS = article('Exposición das modificacións puntuais nº 6 e nº 7', '''
<p>Expostas ata o día 28 de maio</p>
<p><strong>Modificación puntual nº 6 do PXOM na delimitación dos núcleos rurais.</strong></p>
<ul><li>Anuncio no DOG → <a href="/MPN6/dog.pdf"></a></li>
<li>Planos → <a href="/MPN6/planos.pdf"></a></li></ul>
<p><strong>Modificación puntual nº 7 do PXOM de modificación das categorías de solo rústico.</strong></p>
<ul><li>Anuncio no DOG → <a href="/MPN7/dog.pdf"></a></li>
<li>Planos → <a href="/MPN7/planos.pdf"></a></li>
<li>Modelo tipo de alegación → <a href="/MPN6/modelo_alegacions_MP-N7.pdf"></a></li></ul>
''')
APE = article('Proyecto de reparcelación APE-4', '''
<ul><li><a href="/2026/Proy_Reparc_APE4_Tomo_1.pdf">Tomo 1</a></li>
<li><a href="/2026/Proy_Reparc_APE4_Tomo_2.pdf">Tomo 2</a></li>
<li><a href="/2026/Proy_Reparc_APE4_Tomo_3.pdf">Tomo 4</a></li></ul>
''')


class CurtisTests(unittest.TestCase):
    def test_inventory_scope_and_deduplication(self):
        urls, excluded = parse_inventory(INVENTORY)
        self.assertEqual(len(urls), 2)
        self.assertEqual(len(excluded), 1)
        self.assertTrue(all(u.startswith('https://curtis.gal/') for u in urls))

    def test_two_instruments_not_five_documents_or_a_licence(self):
        rows = parse_detail(MODIFICATIONS, SOURCE)
        self.assertEqual([r['id'] for r in rows], ['curtis-proy-pxom-mp-6', 'curtis-proy-pxom-mp-7'])
        self.assertEqual([len(r['documentos']) for r in rows], [2, 3])
        self.assertIn('MPN6/modelo_alegacions_MP-N7.pdf', rows[1]['documentos'][-1]['url'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertNotIn('fase', rows[0])

    def test_ape_volumes_grouped_and_original_label_preserved(self):
        rows = parse_detail(APE, SOURCE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['documentos'][-1]['titulo'], 'Tomo 4')
        self.assertTrue(rows[0]['documentos'][-1]['url'].endswith('Tomo_3.pdf'))
        self.assertIsNone(rows[0]['fecha_publicacion'])  # 2026 path is not a date
        self.assertIsNone(rows[0]['geometry'])

    def test_pagination_fails_explicitly(self):
        for navigation in ['<a rel="next" href="?page=2">2</a>',
                           '<div class="pagination"><a href="?start=10">2</a></div>',
                           '<a href="?page=2">Seguinte</a>']:
            with self.subTest(navigation=navigation), self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(INVENTORY + navigation)

    def test_fail_on_missing_or_unassigned_documents(self):
        for html in [article('Proyecto de reparcelación APE-4', '<p>No documentos</p>'),
                     MODIFICATIONS.replace('</div>', '<a href="/extra.pdf">Extra</a></div>'),
                     article('Formulario de licencia', '<a href="/modelo.pdf">Formulario</a>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, SOURCE)
        with self.assertRaises(ValueError):
            parse_inventory('<html>Maintenance</html>')

    def test_snapshot_and_failure_preserves_previous_output(self):
        adapter = CurtisAyuntamientoAdapter('curtis')
        pages = {SOURCE: INVENTORY, 'https://curtis.gal/index.php/es/aviso/modificaciones': MODIFICATIONS,
                 'https://curtis.gal/index.php/es/aviso/ape': APE}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 3)
            previous = output.read_text()
            self.assertEqual(len([json.loads(line) for line in previous.splitlines()]), 3)
            with patch.object(adapter, '_fetch', return_value='Maintenance'), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), previous)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('curtis')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CurtisAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
