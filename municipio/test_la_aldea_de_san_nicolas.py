import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.la_aldea_de_san_nicolas import (
    API, DATASET, LaAldeaDeSanNicolasAyuntamientoAdapter,
    parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

INDEX = 'https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/LAld/convento/indice.html'
TITLE = ('Aprobación Definitiva de Adaptación del Plan General de Ordenación '
         'en El Convento de La Aldea de San Nicolás')


def payload():
    resources = [
        {'id': 'doc-index', 'name': TITLE + ', publicado el 19/07/2017 en el BOC 138/17',
         'url': INDEX, 'format': 'HTML', 'description': 'Documentos de ' + TITLE},
        {'id': 'sipu', 'name': TITLE + ', publicado el 19/07/2017 en el BOC 138/17',
         'url': 'https://opendata.sitcan.es/upload/plan.zip', 'format': 'ZIP'},
        {'id': 'form', 'name': 'Solicitud de licencia de obras',
         'url': 'https://opendata.sitcan.es/form.pdf'},
    ]
    return {'success': True, 'result': {'name': DATASET, 'state': 'active',
            'num_resources': len(resources), 'resources': resources}}


class ParserTests(unittest.TestCase):
    def test_groups_distributions_and_preserves_provenance_without_dates(self):
        rows = parse_inventory(payload())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['distribuciones']), 2)
        self.assertEqual(row['codigo_ine'], '35020')
        self.assertEqual(row['url'], INDEX)
        self.assertIn('publicado el 19/07/2017', row['distribuciones'][0]['titulo'])
        for field in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, row)
        p = payload()
        p['result']['resources'].reverse()
        self.assertEqual(row['id'], parse_inventory(p)[0]['id'])

    def test_rejects_incomplete_wrong_empty_and_external_sources(self):
        variants = []
        p = payload(); p['result']['num_resources'] += 1; variants.append(p)
        p = payload(); p['result']['name'] = 'another-town'; variants.append(p)
        p = payload(); p['success'] = False; variants.append(p)
        p = payload(); p['result']['resources'] = []; p['result']['num_resources'] = 0; variants.append(p)
        p = payload(); p['result']['resources'][0]['url'] = 'https://example.org/plan'; variants.append(p)
        p = payload(); p['result']['resources'][0]['name'] = 'Formulario'; variants.append(p)
        for p in variants:
            with self.subTest(payload=p), self.assertRaises(ValueError):
                parse_inventory(p)

    def test_separate_instruments_and_document_boundaries(self):
        p = payload()
        other = copy.deepcopy(p['result']['resources'][0])
        other.update(id='other', name=TITLE.replace('El Convento', 'Los Caserones'),
                     url=INDEX.replace('convento', 'caserones'))
        p['result']['resources'].append(other); p['result']['num_resources'] += 1
        rows = parse_inventory(p)
        self.assertEqual(sorted(len(r['distribuciones']) for r in rows), [1, 2])
        docs = parse_documents('<a href="TNP/plan.pdf">Certificado</a>' * 2, INDEX)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['source_index'], INDEX)
        for html in ['', '<a href="../caserones/p.pdf">otro</a>', '<a rel="next" href="p2">Más</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_documents(html, INDEX)

    def test_live_path_mocked_and_failure_preserves_previous_output(self):
        adapter = LaAldeaDeSanNicolasAyuntamientoAdapter('la-aldea-de-san-nicolas')
        inventory = Mock(url=API, content=b'{}'); inventory.json.return_value = payload()
        index = Mock(url=INDEX, content=b'<a href="TNP/plan.pdf">Plan</a>')
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'proyectos.jsonl'
            with patch('municipio.adapters.la_aldea_de_san_nicolas.requests.get', side_effect=[inventory, index]):
                self.assertEqual(adapter.backfill_proyectos(out)['count'], 1)
            original = out.read_bytes()
            self.assertEqual(len(json.loads(original)['documentos']), 1)
            index.content = b'no documents'
            with patch('municipio.adapters.la_aldea_de_san_nicolas.requests.get', side_effect=[inventory, index]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), original)
            lic = Path(temp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(lic)['disabled'])
            self.assertEqual(lic.read_text(), '')

    def test_manifest(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/la-aldea-de-san-nicolas/manifest.yaml'
        raw = load_yaml(path)
        self.assertEqual(raw['codigo_ine'], '35020')
        self.assertEqual(raw['provincia'], 'Las Palmas')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(load_manifest(path).licencias.enabled)


if __name__ == '__main__':
    unittest.main()
