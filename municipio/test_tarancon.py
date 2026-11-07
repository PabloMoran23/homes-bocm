import tempfile
import unittest
from pathlib import Path

from municipio.adapters.tarancon import TaranconAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


MP = 'Modificaciones Puntuales a las Normas Subsidiarias'
ED = 'Estudios de Detalle'


def page(body):
    return '<main id="content">8.3. NORMATIVA URBANÍSTICA' + body + '</main>'


def doc(identifier, title, description=''):
    return f'<a href="https://tarancon.sedelectronica.es/preview-document/{identifier}" title="{description}">{title}</a>'


def fixtures():
    folders = ''.join(f'''<a class="exp" onclick="wicketAjaxGet('../../?x=public')">{name} ( {count} )</a>'''
                      for name, count in [(MP, 1), (ED, 3)])
    root = page(folders + doc('a', 'Tomo I: NORMAS SUBSIDIARIAS DE TARANCÓN')
                + doc('b', 'Tomo II: NORMAS SUBSIDIARIAS DE TARANCÓN')
                + doc('c', 'Tomo III: NORMAS SUBSIDIARIAS DE TARANCÓN')
                + doc('guide', 'GUÍA DEL PATRIMONIO HISTÓRICO-ARTÍSTICO DE TARANCÓN (04/1995)'))
    pages = {MP: page(doc('mp', 'URB MP Nº 28 OR-10 BOP 20250806')),
             ED: page(doc('ed1', 'URB ED MANZANA NORIA memoria')
                      + doc('ed2', 'URB ED MANZANA NORIA planos')
                      + doc('ed3', 'URB ED MANZANA NORIA DOCM 20231027',
                            'Acuerdo del Pleno, de fecha 11/10/2023, por el que se aprueba definitivamente expediente de estudio de detalle.'))}
    return root, pages


class TaranconTests(unittest.TestCase):
    def test_grouping_and_date_provenance(self):
        rows = parse_inventory(*fixtures())
        self.assertEqual(len(rows), 3)
        norms = next(r for r in rows if r['tipo'] == 'Normas Subsidiarias')
        self.assertEqual(len(norms['documentos']), 3)
        ed = next(r for r in rows if r['tipo'] == 'Estudio de detalle')
        self.assertEqual(len(ed['documentos']), 3)
        self.assertEqual(ed['fecha_publicacion'], '2023-10-27')
        self.assertEqual(ed['fecha_acuerdo'], '2023-10-11')
        self.assertEqual(ed['fecha_aprob'], '2023-10-11')
        mp = next(r for r in rows if r['tipo'] == 'Modificación puntual')
        self.assertEqual(mp['fecha_publicacion'], '2025-08-06')
        self.assertIsNone(mp['fecha_aprob'])
        self.assertIsNone(mp['fase'])
        for row in rows:
            self.assertIsNone(row['fecha'])
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['lon'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['source_entity_type'], 'documento')
            self.assertEqual(row['codigo_ine'], '16203')

    def test_separate_instruments_and_stable_ids(self):
        root, pages = fixtures()
        root = root.replace('Estudios de Detalle ( 3 )', 'Estudios de Detalle ( 4 )')
        pages[ED] = pages[ED].replace('</main>', doc('other', 'URB ED MANZANA OTRA planos') + '</main>')
        rows = parse_inventory(root, pages)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r['id'] for r in rows}), 4)
        original = {r['titulo']: r['id'] for r in parse_inventory(*fixtures())}
        self.assertTrue(all(r['id'] == original[r['titulo']] for r in rows if r['titulo'] in original))

    def test_incomplete_and_changed_sources_fail(self):
        root, pages = fixtures()
        for changed_root, changed_pages in [('', pages), (root, {}),
                (root, {**pages, ED: page('')}),
                (root, {**pages, ED: pages[ED].replace('</main>', '<a rel="next">Next</a></main>')}),
                (root, {**pages, MP: page(doc('form', 'Solicitud de licencia urbanística'))})]:
            with self.subTest(changed_pages=changed_pages), self.assertRaises(ValueError):
                parse_inventory(changed_root, changed_pages)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tarancon')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Tarancón', 'Cuenca', '16203'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = TaranconAyuntamientoAdapter('tarancon').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
