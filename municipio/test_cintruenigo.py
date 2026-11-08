import copy
import json
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.cintruenigo import (
    CintruenigoAyuntamientoAdapter, collect_inventory, parse_instrument,
)
from municipio.manifest import load_manifest, load_yaml


def instrument():
    return {
        'idInstrumento': 3451, 'denominacion': 'PLAN MUNICIPAL',
        'tipoInstrumento': {'denominacion': 'Plan Municipal'},
        'instrumentosMunicipios': [{'idProvincia': 31, 'idMunicipio': 72,
                                   'municipio': {'denominacion': 'CINTRUÉNIGO'}}],
        'fechaDefinitiva': '1998-12-28T00:00:00',
        'instrumentosDocumentos': [
            {'idDocumento': 2019, 'denominacion': 'Memoria Justificativa',
             'idTipoDocumento': 1,
             'rutaFichero': 'https://administracionelectronica.navarra.es/SIUN_Consulta/SIUN_DOCUMENTOS/PM/003451/3451_001.pdf'},
            {'idDocumento': 2025, 'denominacion': 'Situación de la Comarca',
             'idTipoDocumento': 2,
             'rutaFichero': 'https://gissiun.tracasa.es/navegar/iframeLegend.aspx?CODMUN=72'}],
        'tramites': [{'idTramite': 12246, 'fase': {'denominacion': 'Definitiva'},
                      'resolucion': {'denominacion': 'Aprobación'},
                      'fecha': '1998-12-28T00:00:00', 'fechaResolucion': None,
                      'numBon': 155, 'numAnuncio': 16}],
    }


class CintruenigoTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        data = instrument()
        data['instrumentosDocumentos'].append(copy.deepcopy(data['instrumentosDocumentos'][0]))
        row = parse_instrument(data, 3451)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['tramites'][0]['fecha_publicacion'], '1998-12-28T00:00:00')
        self.assertIsNone(row['tramites'][0]['fecha_resolucion'])
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertNotIn('lat', row)
        self.assertEqual(row['codigo_ine'], '31072')

    def test_wrong_municipality_or_identity_rejected(self):
        data = instrument()
        with self.assertRaises(ValueError):
            parse_instrument(data, 9)
        data['instrumentosMunicipios'][0]['idMunicipio'] = 73
        with self.assertRaises(ValueError):
            parse_instrument(data, 3451)

    def test_instrument_without_documents_is_retained(self):
        data = instrument()
        data['instrumentosDocumentos'] = []
        self.assertEqual(parse_instrument(data, 3451)['documentos'], [])

    def test_all_pages(self):
        calls = []
        def fetch(path, filters):
            calls.append(path)
            self.assertEqual(filters['municipios'], [72])
            self.assertFalse(filters['aprobadoPosterior'])
            start = int(path.split('/')[-2])
            return {'pagedInfo': {'totalElements': 27, 'pageSize': 25},
                    'currentPage': [{'idInstrumento': n} for n in range(start, min(start+25, 27))]}
        self.assertEqual(len(collect_inventory(fetch)), 27)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].endswith('/25/25'))

    def test_pagination_failures(self):
        for mode in ('empty', 'repeat', 'changed'):
            def fetch(path, filters):
                start = int(path.split('/')[-2])
                page = [{'idInstrumento': n} for n in range(25)]
                if start:
                    page = [] if mode == 'empty' else [{'idInstrumento': 0}]
                return {'pagedInfo': {'totalElements': 28 if start and mode == 'changed' else 27,
                                      'pageSize': 25}, 'currentPage': page}
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                collect_inventory(fetch)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cintruenigo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '31072')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = CintruenigoAyuntamientoAdapter('cintruenigo')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')

    def test_output_preserves_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            row = parse_instrument(instrument(), 3451)
            CintruenigoAyuntamientoAdapter._write(path, [row])
            self.assertEqual(json.loads(path.read_text()), row)


if __name__ == '__main__':
    unittest.main()
