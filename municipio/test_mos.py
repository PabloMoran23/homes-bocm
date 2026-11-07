import copy
import unittest

from municipio.adapters.mos import MosAyuntamientoAdapter as Adapter


class MosParserTests(unittest.TestCase):
    def setUp(self):
        self.item = dict(id='28057', docnome='PLAN XERAL DE MOS', figura='Plan Xeral',
                         fechaaddef='2017-01-18', fechabop='2017-06-02',
                         fechadog='2017-02-08', fechanormativabop=None)
        general = {**self.item, 'menutitle': 'Mos',
                   'filesroot': 'documentos/urbanismo/', 'folder': 'MOS'}
        self.detail = {'datos_xerais': general, 'incidencias_iuris': ['Source legal observation'],
                       'elementos': [dict(description='Memoria', componentes=[
                           dict(id='1', pathesperado='plan.pdf', descripcion='Memoria'),
                           dict(id='2', pathesperado='map.jpg', descripcion='Plano')])]}

    def test_dates_and_provenance_grouped(self):
        row = Adapter.parse_detail(self.item, self.detail, '14')
        self.assertEqual(row['fecha_aprob'], '2017-01-18')
        self.assertEqual(row['fecha_publicacion_dog'], '2017-02-08')
        self.assertEqual(row['fecha_publicacion_bop'], '2017-06-02')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'],
                         'https://siotuga.xunta.gal/siotuga/documentos/urbanismo/MOS/documents/plan.pdf')
        self.assertEqual(row['incidencias_juridicas'], ['Source legal observation'])

    def test_missing_dates_are_not_inferred(self):
        for field in ('fechaaddef', 'fechabop', 'fechadog'):
            self.item[field] = self.detail['datos_xerais'][field] = None
        row = Adapter.parse_detail(self.item, self.detail, '14')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])

    def test_reject_envelopes_forms_duplicates_and_invalid_dates(self):
        for payload in ({'results': [self.item], 'next': 2}, '<form>Licence</form>',
                        [self.item, self.item], [{'id': '2', 'docnome': 'Form'}],
                        [{**self.item, 'fechaaddef': '2017-02-30'}]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                Adapter.parse_inventory(payload)

    def test_all_rows_no_pagination_slice(self):
        items = [{**self.item, 'id': str(i)} for i in range(100)]
        self.assertEqual(len(Adapter.parse_inventory(items)), 100)

    def test_document_deduplication(self):
        self.detail['elementos'].append(copy.deepcopy(self.detail['elementos'][0]))
        self.assertEqual(len(Adapter.parse_detail(self.item, self.detail, '14')['documentos']), 2)

    def test_explicit_null_documents_retains_real_instrument(self):
        self.detail['elementos'] = None
        row = Adapter.parse_detail(self.item, self.detail, '14')
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['documentos_estado'], 'sin documentos en SIOTUGA')
        del self.detail['elementos']
        with self.assertRaises(ValueError):
            Adapter.parse_detail(self.item, self.detail, '14')

    def test_wrong_municipality_identity_or_date_fails(self):
        for field, value in [('menutitle', 'Vigo'), ('id', '999'), ('fechadog', None)]:
            detail = copy.deepcopy(self.detail)
            detail['datos_xerais'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                Adapter.parse_detail(self.item, detail, '14')


if __name__ == '__main__':
    unittest.main()
