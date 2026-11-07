import unittest
from municipio.adapters.foz import parse_inventory, parse_detail, build_records
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def instrument(key='28131'):
    return {'id': key, 'docnome': 'Plan Xeral de Ordenación Municipal de Foz',
            'figura': 'Plan Xeral', 'fechaaddef': '2018-09-18',
            'fechabop': '2018-12-13', 'fechadog': '2018-10-04',
            'fechanormativabop': None, 'inventory_class': 14}


def detail(key='28131'):
    return {'datos_xerais': {'id': key, 'folder': 'FOZ', 'filesroot': 'documentos/urbanismo/'},
            'elementos': [{'description': 'Normativa', 'componentes': [
                {'pathesperado': key + 'nu001.pdf', 'descripcion': 'Normativa'}]}]}


class FozTests(unittest.TestCase):
    def test_inventory_complete_array_and_dedup(self):
        rows = [instrument(str(i)) for i in range(60)]
        self.assertEqual(len(parse_inventory(rows + rows)), 60)
        for value in ({'data': rows, 'next': 2}, {'error': 'denied'}, [dict(instrument(), fechaaddef='bad')]):
            with self.assertRaises(ValueError):
                parse_inventory(value)

    def test_detail_identity_and_document_links(self):
        docs = parse_detail(detail(), '28131')
        self.assertEqual(docs[0]['url'], 'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/FOZ/documents/28131nu001.pdf')
        bad = detail(); bad['datos_xerais']['folder'] = 'OTHER'
        with self.assertRaises(ValueError):
            parse_detail(bad, '28131')
        missing = detail(); missing['elementos'] = None
        self.assertEqual(parse_detail(missing, '28131'), [])
        bad = detail(); bad['elementos'] = []
        with self.assertRaises(ValueError):
            parse_detail(bad, '28131')

    def test_group_pxom_and_preserve_dates(self):
        first = instrument(); second = instrument('28708')
        second.update(fechaaddef='2025-04-21', fechadog='2025-05-05', fechabop='2025-06-09')
        rows = build_records([first, second], {k: parse_detail(detail(k), k) for k in ('28131', '28708')})
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['expedientes_fuente'][0]['fecha_aprob'], '2018-09-18')
        self.assertNotIn('fecha_aprob', rows[0]['expedientes_fuente'][1])
        self.assertEqual(rows[0]['expedientes_fuente'][1]['fecha_publicacion_dog'], '2025-05-05')
        self.assertNotIn('lat', rows[0]); self.assertNotIn('fecha', rows[0])
        with self.assertRaises(ValueError):
            build_records([], {})

    def test_source_chronology_not_silently_fixed(self):
        item = instrument('27728'); item['fechaaddef'] = '2012-12-29'; item['fechabop'] = '2012-01-25'
        row = build_records([item], {'27728': parse_detail(detail('27728'), '27728')})[0]
        self.assertIn('chronology_warning', row['expedientes_fuente'][0])
        self.assertEqual(row['expedientes_fuente'][0]['fecha_aprob'], '2012-12-29')

    def test_manifest_adapter(self):
        manifest = load_manifest('foz')
        self.assertEqual(manifest.provincia, 'Lugo')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(load_portal_adapter(manifest).slug, 'foz')


if __name__ == '__main__':
    unittest.main()
