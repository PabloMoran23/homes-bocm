"""Parser and pagination regressions; no network used by these tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.macanet_de_la_selva import (
    API, MUNICIPIO, MacanetDeLaSelvaAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def item(code='36758', municipality=MUNICIPIO):
    return {'codi': code, 'municipi': municipality, 'vigencia': 'SI'}


def detail():
    return {'codintExp': 36758, 'municipi': MUNICIPIO,
            'tema': "revisió del Pla general d'ordenació", 'codiRang': 'PG',
            'tipologiaCA': 'Revisió pla general ordenació urbana municipal',
            'numComplet': '2001 / 000500 / G',
            'dataAprovacio': '2002-05-28', 'dataPublicacio': '2002-07-18',
            'documents': [{'idDocument': 127180, 'nomDocument': 'Memòria.pdf'},
                          {'idDocument': 218247, 'nomDocument': 'Normes.pdf'}],
            'assentaments': [{'dataAssentament': '2007-12-20'}]}


class MacanetTests(unittest.TestCase):
    def test_dates_documents_identity_and_no_invented_geometry(self):
        row = Adapter.parse_project(item(), detail())
        self.assertEqual(row['fecha_aprob'], '2002-05-28')
        self.assertEqual(row['fecha_publicacion'], '2002-07-18')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn(API + 'documents?documentId=127180', row['documentos'][0]['url'])
        self.assertEqual(row['codigo_ine'], '17103')
        self.assertEqual(row['id'], Adapter.parse_project(item(), detail())['id'])

    def test_missing_dates_stay_missing(self):
        data = detail()
        data.update(dataAprovacio=None, dataPublicacio=None)
        row = Adapter.parse_project(item(), data)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_bad_detail_identity_schema_and_date_rejected(self):
        for changes in ({'codintExp': 42}, {'municipi': 'Girona'}, {'tema': ''},
                        {'codiRang': 'OTHER'}, {'documents': None},
                        {'dataAprovacio': '2025-02-30'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Adapter.parse_project(item(), {**detail(), **changes})

    def test_one_based_pagination_and_complete_total(self):
        adapter = Adapter('macanet-de-la-selva')
        batch = [item(str(n)) for n in range(1, 21)]
        pages = [{'totals': 21, 'llistat': batch, 'infoFiltre': MUNICIPIO},
                 {'totals': 21, 'llistat': [item('21')], 'infoFiltre': MUNICIPIO}]
        with patch.object(adapter, '_get', side_effect=pages) as get:
            self.assertEqual(len(adapter.inventory()), 21)
            self.assertEqual([c.args[1]['firstRecord'] for c in get.call_args_list], [1, 2])

    def test_truncation_duplicates_changing_totals_filter_rejected(self):
        adapter = Adapter('macanet-de-la-selva')
        first = {'totals': 21, 'llistat': [item(str(n)) for n in range(1, 21)],
                 'infoFiltre': MUNICIPIO}
        for second in ({'totals': 21, 'llistat': [], 'infoFiltre': MUNICIPIO},
                       {'totals': 21, 'llistat': [item('1')], 'infoFiltre': MUNICIPIO},
                       {'totals': 22, 'llistat': [item('21')], 'infoFiltre': MUNICIPIO},
                       {'totals': 21, 'llistat': [item('21')], 'infoFiltre': 'Girona'}):
            with self.subTest(second=second), patch.object(adapter, '_get', side_effect=[first, second]), self.assertRaises(ValueError):
                adapter.inventory()
        with patch.object(adapter, '_get', return_value={**first, 'llistat': [item()]}), self.assertRaises(ValueError):
            adapter.inventory()

    def test_snapshot_groups_documents_excludes_regional_and_preserves_on_failure(self):
        adapter = Adapter('macanet-de-la-selva')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            with patch.object(adapter, 'inventory', return_value=[item(), item('9', 'Girona')]), patch.object(adapter, '_get', return_value=detail()):
                result = adapter.update_proyectos(out, Path(folder) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(result['excluded_regional']), 1)
            original = out.read_text()
            with patch.object(adapter, 'inventory', return_value=[item()]), patch.object(adapter, '_get', return_value={}):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)

    def test_tuc_is_instrument_and_agreement_is_excluded(self):
        tuc = {**detail(), 'codiRang': 'TUC', 'tipologiaCA': 'Delimitació de la TUC'}
        self.assertEqual(Adapter.parse_project(item(), tuc)['tipo'], 'Delimitació de la TUC')
        adapter = Adapter('macanet-de-la-selva')
        agreement = {**detail(), 'codintExp': 9, 'codiRang': 'CNV'}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(adapter, 'inventory', return_value=[item(), item('9')]), patch.object(adapter, '_get', side_effect=[detail(), agreement]):
                result = adapter.backfill_proyectos(Path(folder) / 'proyectos.jsonl')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['excluded_agreements'][0]['rpuc_id'], '9')

    def test_manifest_loads_and_disables_licences_schedule_jitter(self):
        manifest = load_manifest('macanet-de-la-selva')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '17103')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
