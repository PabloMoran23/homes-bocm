import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.calonge_i_sant_antoni import (
    CalongeISantAntoniAyuntamientoAdapter as Adapter, SOURCE, SECTIONS,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    return {
        'data': [{
            'type': 'poum', 'id': 'plan-1',
            'attributes': {
                'title': "Pla d'Ordenació Urbanística Municipal",
                'description': {'value': '<p>Regulat per la Llei 3/2012, de 22 de febrer.</p>'},
                'other_links': [{'title': "Pla d'Ordenació Urbanística", 'uri':
                    'http://tes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=veureFitxa&amp;codiPublic=2009/39204/G'}],
            },
            'relationships': {s: {'data': [{'type': 'file', 'id': 'doc-1', 'meta': {
                'description': "Acord d'aprovació definitiva"}}] if s == 'regulations_files' else []} for s in SECTIONS},
        }],
        'included': [{'type': 'file', 'id': 'doc-1', 'attributes': {
            'filename': 'poumdef.pdf', 'filemime': 'application/pdf',
            'uri': {'url': '/sites/default/files/files/poumdef.pdf'},
        }}], 'links': {},
    }


def response(page, url):
    result = Mock()
    result.url = url
    result.iter_content.return_value = [json.dumps(page).encode()]
    context = Mock()
    context.__enter__ = Mock(return_value=result)
    context.__exit__ = Mock(return_value=False)
    return context


class CalongeTests(unittest.TestCase):
    def test_grouping_provenance_and_date_semantics(self):
        page = fixture()
        page['data'][0]['relationships']['gc_files']['data'] = copy.deepcopy(
            page['data'][0]['relationships']['regulations_files']['data'])
        rows = Adapter.parse_inventory([page])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['expediente'], '2009/39204/G')
        self.assertEqual(row['codigo_ine'], '17034')
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(len(row['documentos'][0]['secciones']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])

    def test_empty_form_and_missing_document_fail(self):
        bad = [fixture() for _ in range(4)]
        bad[0]['data'] = []
        bad[1]['data'][0]['attributes']['title'] = 'Sol·licitud de llicència'
        bad[2]['included'] = []
        bad[3]['data'][0]['relationships']['gc_files']['links'] = {'next': {'href': '?page=2'}}
        for page in bad:
            with self.subTest(page=page), self.assertRaises(ValueError):
                Adapter.parse_inventory([page])

    def test_live_crawler_follows_next_and_update_refreshes(self):
        first, second = fixture(), fixture()
        first['included'] = []  # inclusion may be resolved on a later page
        next_url = SOURCE + '&page[offset]=1'
        first['links']['next'] = {'href': next_url.replace('https:', 'http:')}
        second['data'] = []
        with tempfile.TemporaryDirectory() as tmp, patch(
            'municipio.adapters.calonge_i_sant_antoni.requests.get',
            side_effect=[response(first, SOURCE), response(second, next_url)],
        ) as get:
            path = Path(tmp) / 'projects.jsonl'
            result = Adapter('calonge-i-sant-antoni').update_proyectos(path, Path(tmp) / 'state')
            self.assertEqual(get.call_count, 2)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['source_urls'], [SOURCE, next_url])
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_cycle_and_foreign_pagination_preserve_existing_output(self):
        for next_url in (SOURCE, 'https://example.org/jsonapi/node/poum'):
            page = fixture()
            page['links']['next'] = {'href': next_url}
            with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.calonge_i_sant_antoni.requests.get',
                return_value=response(page, SOURCE),
            ):
                path = Path(tmp) / 'projects.jsonl'
                path.write_text('previous snapshot')
                with self.assertRaises(ValueError):
                    Adapter('calonge-i-sant-antoni').backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_resolves_and_licences_disabled(self):
        manifest = load_manifest('calonge-i-sant-antoni')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
