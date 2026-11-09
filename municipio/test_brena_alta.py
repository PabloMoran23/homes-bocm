"""Parser and snapshot tests, offline and independent of live evidence files."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.brena_alta import (
    API, DATASET, INDEX_ROOT, BrenaAltaAyuntamientoAdapter,
    parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def fixture():
    resources = []
    for n, title in enumerate([
        'Aprobación Definitiva de Plan General de Ordenación de Breña Alta',
        'Aprobación definitiva de Modificación Puntual de sectores SUNSE-1 y SUNSD-1 Bajamar de Plan General de Ordenación de Breña Alta por pleno COTMAC 23/12/2011',
    ]):
        for kind, url in [('HTML', INDEX_ROOT + str(n) + '/indice.html'),
                          ('ZIP', 'https://opendata.sitcan.es/upload/' + str(n) + '.zip')]:
            resources.append({'id': str(n) + kind, 'name': title, 'url': url, 'format': kind,
                              'description': 'Documentación de ' + title + ', publicado el 23/01/2012 en el BOC 015/12 y el 08/02/2012 en el BOP 022/12',
                              'created': '2026-01-01', 'metadata_modified': '2026-02-01'})
    return {'success': True, 'result': {'name': DATASET, 'state': 'active',
            'title': 'Planeamiento urbanístico de Breña Alta',
            'num_resources': len(resources), 'resources': resources}}


class BrenaAltaTests(unittest.TestCase):
    def test_grouping_retains_all_distributions_and_dates(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(len(r['distributions']) == 2 for r in rows))
        self.assertNotIn('fecha_acuerdo', rows[0])
        self.assertEqual(rows[1]['fecha_acuerdo'], '2011-12-23')
        self.assertEqual(rows[1]['publicaciones'], [
            {'fecha': '2012-01-23', 'boletin': 'BOC', 'referencia': '015/12'},
            {'fecha': '2012-02-08', 'boletin': 'BOP', 'referencia': '022/12'}])
        for row in rows:
            for field in ['fecha', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase']:
                self.assertNotIn(field, row)
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '38008')

    def test_order_independence_and_stable_identity(self):
        data = fixture()
        first = parse_inventory(data)
        data['result']['resources'].reverse()
        self.assertEqual(first, parse_inventory(data))

    def test_bad_inventories_fail(self):
        mutations = [
            lambda p: p.update(success=False),
            lambda p: p['result'].update(num_resources=20),
            lambda p: p['result'].update(resources=[], num_resources=0),
            lambda p: p['result'].update(title='Planeamiento urbanístico de Breña Baja'),
            lambda p: p['result']['resources'][0].update(name='Instancia obra mayor'),
            lambda p: p['result']['resources'][0].update(name='Anuncio de licitación de obras'),
            lambda p: p['result']['resources'][0].update(url='https://example.org/indice.html'),
            lambda p: p['result']['resources'][0].update(id='0ZIP'),
            lambda p: p['result']['resources'][0].update(url='https://geobdp.grafcan.es/core/documentos/9/'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                payload = copy.deepcopy(fixture())
                mutation(payload)
                with self.assertRaises(ValueError):
                    parse_inventory(payload)

    def test_document_links_stay_with_instrument(self):
        html = '<a href="TNP/norma.pdf">Normativa</a><a href="POP/plano.pdf">Plano</a><a href="TNP/norma.pdf">Normativa</a>'
        url = INDEX_ROOT + '458/indice.html'
        docs = parse_documents(html, url)
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(d['source_url'] == url for d in docs))
        self.assertTrue(all(d['url'].startswith(INDEX_ROOT + '458/') for d in docs))
        for bad in ['<a href="../459/TNP/otro.pdf">Otro plan</a>',
                    '<a href="form.doc">Formulario</a>',
                    html + '<a rel="next" href="?page=2">Siguiente</a>']:
            with self.assertRaises(ValueError):
                parse_documents(bad, url)

    def test_snapshot_not_written_on_partial_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous complete snapshot')
            adapter = BrenaAltaAyuntamientoAdapter('brena-alta')
            with patch.object(adapter, '_get', side_effect=[json.dumps(fixture()).encode(), b'<a href="doc.pdf">Doc</a>', b'changed markup']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous complete snapshot')

    def test_backfill_update_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'records.jsonl'
            adapter = BrenaAltaAyuntamientoAdapter('brena-alta')
            def get(url):
                return json.dumps(fixture()).encode() if url == API else b'<a href="doc.pdf">Doc</a>'
            with patch.object(adapter, '_get', side_effect=get):
                self.assertEqual(adapter.backfill_proyectos(out)['count'], 2)
                before = out.read_bytes()
                adapter.update_proyectos(out, Path(tmp) / 'state.json')
                self.assertEqual(before, out.read_bytes())
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('brena-alta')
        self.assertEqual(manifest.provincia, 'Santa Cruz de Tenerife')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.brena_alta:BrenaAltaAyuntamientoAdapter')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '38008')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
