import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.berriozar import BerriozarAyuntamientoAdapter, BASE, parse_instrument, parse_page
from municipio.manifest import load_manifest, load_yaml


def detail(key=10):
    return {
        'idInstrumento': key, 'denominacion': 'PARCELA 1',
        'tipoInstrumento': {'denominacion': 'Estudio de Detalle'},
        'instrumentosMunicipios': [{'idProvincia': 31, 'idMunicipio': 903,
                                   'municipio': {'denominacion': 'BERRIOZAR'}}],
        'instrumentosDocumentos': [
            {'idDocumento': 1, 'denominacion': 'Memoria', 'rutaFichero': BASE + 'memoria.pdf'},
            {'idDocumento': 2, 'denominacion': 'Plano', 'rutaFichero': BASE + 'plano.pdf'}],
        'fechaDefinitiva': '2020-01-02T00:00:00',
        'tramites': [
            {'idTramite': 1, 'fase': {'denominacion': 'Definitiva'},
             'resolucion': {'denominacion': 'Aprobación'}, 'fecha': '2020-02-03T00:00:00',
             'fechaResolucion': '2020-01-20T00:00:00', 'numBon': 20, 'numAnuncio': 4}],
    }


class BerriozarTests(unittest.TestCase):
    def test_document_grouping_and_date_semantics(self):
        data = detail()
        data['instrumentosDocumentos'].append(copy.deepcopy(data['instrumentosDocumentos'][0]))
        row = parse_instrument(data, 10)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_publicacion'], '2020-02-03')
        self.assertEqual(row['fecha_aprob'], '2020-01-20')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['tramites'][0]['url_bon'], 'https://bon.navarra.es/es/anuncio/-/texto/2020/20/4')
        data['tramites'][0]['fechaResolucion'] = None
        self.assertIsNone(parse_instrument(data, 10)['fecha_aprob'])
        data['tramites'][0]['numBon'] = None
        self.assertIsNone(parse_instrument(data, 10)['fecha_publicacion'])

    def test_reject_wrong_municipality_and_id(self):
        data = detail()
        data['instrumentosMunicipios'][0]['idMunicipio'] = 902
        with self.assertRaises(ValueError):
            parse_instrument(data, 10)
        with self.assertRaises(ValueError):
            parse_instrument(detail(), 11)

    def test_reject_invalid_pagination(self):
        for info in [dict(pageSize=25, totalElements=26, totalPages=1),
                     dict(pageSize=25, totalElements=0, totalPages=0)]:
            with self.assertRaises(ValueError):
                parse_page({'currentPage': [], 'pagedInfo': info})

    def test_all_pages_and_fail_atomic_on_repeat(self):
        class Response:
            def __init__(self, value):
                self.value = value
                self.content = (value if isinstance(value, str) else json.dumps(value)).encode()
            def raise_for_status(self):
                pass
            def json(self):
                return self.value

        class Session:
            def __init__(self):
                self.headers = {}
                self.offsets = []
                self.repeat = False
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def get(self, url, **kwargs):
                if url.endswith('api/Municipios'):
                    return Response([{'idMunicipio': 903, 'denominacion': 'BERRIOZAR'}])
                if '/api/Instrumentos/' in url:
                    return Response(detail(int(url.rsplit('/', 1)[1])))
                return Response(f'<main><div class="contenido content"><a href="{BASE}Index.html#/inicio">SIUN</a></div></main>')
            def post(self, url, **kwargs):
                offset = int(url.split('/')[-2])
                self.offsets.append(offset)
                key = 10 if offset == 0 or self.repeat else 11
                return Response({'currentPage': [{'idInstrumento': key}],
                                 'pagedInfo': dict(pageSize=1, totalElements=2, totalPages=2)})

        session = Session()
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.berriozar.requests.Session', return_value=session), patch('municipio.adapters.berriozar.time.sleep'):
            output = Path(directory) / 'projects.jsonl'
            adapter = BerriozarAyuntamientoAdapter('berriozar')
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['rows'], 2)
            self.assertEqual(session.offsets, [0, 1])
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([r['siun_id'] for r in rows], [10, 11])
            before = output.read_bytes()
            session.repeat = True
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('berriozar')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('31903', 'Navarra'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = BerriozarAyuntamientoAdapter('berriozar').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
