"""Offline regression tests with fragments of Porcuna's public inventory markup."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from municipio.adapters.porcuna import (
    INVENTORIES, ORIGIN, PorcunaAyuntamientoAdapter, make_record, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

LEAF = ORIGIN + '/transparency/0d027ec0-76d4-4d43-ab6b-d66a0b7fdc41/'
DOC_IDS = (
    'b1ebc1e9-47e0-4f0b-b5bc-dc375cc8f641',
    'ea9cf4d0-c5ca-45c1-8321-0b89ac9a93e2',
    '8a0da563-32fe-4b9a-b491-00633e980417',
)


def document_html(ids=DOC_IDS):
    titles = ('RESOLUCION 2022-0699 [Resolución de Alcaldía de aprobación inicial]',
              'Anuncio en el [Boletín Oficial de la Provincia/Prensa escrita de gran difusión]',
              'ANUNCIO A D ESTUDIO DE DETALLE BOP')
    return '<table class="TransparencyListPanel">' + ''.join(
        f'<tr><td><a><a class="gIconLink" href="{ORIGIN}/preview-document/{key}">{title}</a></a></td></tr>'
        for key, title in zip(ids, titles)) + '</table>'


class PorcunaTests(unittest.TestCase):
    def test_cisneros_documents_grouped_without_invented_dates(self):
        folders, docs = parse_inventory(document_html(), LEAF)
        self.assertFalse(folders)
        row = make_record('ESTUDIO DETALLE AVENIDA CARDENAL CISNEROS 72', LEAF, docs)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual({d['url'].rsplit('/', 1)[1] for d in row['documentos']}, set(DOC_IDS))
        self.assertTrue(all(d['inventory_url'] == LEAF for d in row['documentos']))
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])

    def test_folder_counter_and_session_action(self):
        html = '''<table class="TransparencyListPanel"><a class="gIconLink exp" href="#"
        onclick="var wcall=wicketAjaxGet('../../?x=abc',null);">ESTUDIO DE DETALLE<span> ( 3 )</span></a></table>'''
        folders, docs = parse_inventory(html, LEAF)
        self.assertEqual(folders, [{'title': 'ESTUDIO DE DETALLE', 'count': 3,
                                    'action': ORIGIN + '/?x=abc'}])
        self.assertFalse(docs)

    def test_explicit_pagination_failure(self):
        html = document_html() + '<div class="more_results"><button onclick="next()">Mostrar más</button></div>'
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(html, LEAF)

    def test_login_or_navigation_is_not_an_inventory(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            parse_inventory('<h1>Identifícate</h1><a href="/transparency">Planeamiento</a>', LEAF)

    def test_no_licence_forms_or_asset_census_as_projects(self):
        _, docs = parse_inventory(document_html(), LEAF)
        self.assertIsNone(make_record('CENSO DE INSTALACIONES CON AMIANTO', LEAF, docs))
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            make_record('SOLICITUD LICENCIA DE OBRAS', LEAF, docs)
        self.assertIsNone(make_record('PLANEAMIENTO VIGENTE', LEAF, []))

    def test_external_document_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            parse_inventory(document_html().replace(ORIGIN, 'https://example.org'), LEAF)

    def test_document_count_mismatch_fails(self):
        adapter = PorcunaAyuntamientoAdapter()
        with patch.object(adapter, '_get', return_value=SimpleNamespace(text=document_html(), url=LEAF)):
            with self.assertRaisesRegex(ValueError, 'expected 4, got 3'):
                adapter._walk(LEAF, 'ESTUDIO DETALLE AVENIDA CARDENAL CISNEROS 72', expected=4)

    def test_backfill_failure_preserves_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            adapter = PorcunaAyuntamientoAdapter()
            with patch.object(adapter, '_walk', side_effect=[([], 0), ValueError('partial inventory')]):
                with self.assertRaisesRegex(ValueError, 'partial'):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')

    def test_snapshot_and_update_use_same_inventory(self):
        _, docs = parse_inventory(document_html(), LEAF)
        row = make_record('ESTUDIO DETALLE AVENIDA CARDENAL CISNEROS 72', LEAF, docs)
        adapter = PorcunaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as folder:
            output, state = Path(folder) / 'rows.jsonl', Path(folder) / 'state.json'
            with patch.object(adapter, '_walk', side_effect=[([row], 3), ([], 0)]) as walk:
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['count'], 1)
            self.assertEqual([call.args[0] for call in walk.call_args_list], list(INVENTORIES))
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '23069')
            self.assertFalse(state.exists())
            self.assertTrue(adapter.backfill_licencias(Path(folder) / 'licencias.jsonl')['disabled'])

    def test_manifest_contract(self):
        manifest = load_manifest('porcuna')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Porcuna', 'Jaén', '23069'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.porcuna:PorcunaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
