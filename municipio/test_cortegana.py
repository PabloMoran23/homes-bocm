import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cortegana import (
    CorteganaAyuntamientoAdapter, instrument_url, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def page(code='10606', total=1):
    return {'iTotalDisplayRecords': total, 'iTotalRecords': total, 'aaData': [
        ['HUELVA', 'CORTEGANA', 'NNSS', '29/07/81', 'Adaptado LOUA', '',
         f"<a class='docuPlan' name='{code}' href='#'>documentos</a>", '']]}


def detail(doc='58589', title='Normas Subsidiarias Municipales'):
    fields = {'Figura': title, 'Objeto': '1981',
              'Ámbito Territorial': 'MUNICIPAL - Municipal CORTEGANA',
              'Fecha de Aprobación': '29/07/81', 'Estado': 'Vigente'}
    table = ''.join(f'<tr><td><span class="area-filter-label">{k}:</span></td><td>{v}</td></tr>'
                    for k, v in fields.items())
    entries = [{'nombre': 'Resolución', 'enlace': f'<a href="descargaDocumentos.jsf?doc={doc}">PDF</a>',
                'clave': group} for group in ['22519', '22519Expedienteadministrativo']]
    return '<table>' + table + '</table><script>var mapa=' + json.dumps(entries) + ';</script>'


class Response:
    def __init__(self, data=None, text=''):
        self.data, self.text = data, text
    def json(self):
        return self.data


class CorteganaTests(unittest.TestCase):
    def test_source_identity_and_no_invented_dates(self):
        row = parse_instrument(detail(), '10606')
        self.assertEqual(row['codigo_ine'], '21025')
        self.assertIn('Normas Subsidiarias', row['titulo'])
        self.assertEqual(row['metadatos_fuente']['Fecha de Aprobación'], '29/07/81')
        for absent in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon']:
            self.assertNotIn(absent, row)
        self.assertFalse(row['publication_ready'])

    def test_document_tree_deduplicated_and_isolated(self):
        a = parse_instrument(detail(), '10606')
        b = parse_instrument(detail('90000', 'PAP'), '37291')
        self.assertEqual(len(a['documentos']), 1)
        self.assertEqual(len(a['documentos'][0]['grupos_fuente']), 2)
        self.assertNotEqual(a['documentos'][0]['url'], b['documentos'][0]['url'])
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(a['url'], instrument_url('10606'))

    def test_reject_wrong_municipality_empty_and_missing_documents(self):
        for html in ['', detail().replace('CORTEGANA', 'ARACENA'), detail().split('<script>')[0],
                     detail().replace('descargaDocumentos.jsf', 'https://example.org/file')]:
            with self.assertRaises(ValueError):
                parse_instrument(html, '10606')
        data = page()
        data['aaData'][0][0] = 'BADAJOZ'
        with self.assertRaises(ValueError):
            parse_inventory(data)

    def test_pagination_fetches_every_page(self):
        adapter = CorteganaAyuntamientoAdapter('cortegana')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_request', side_effect=[
            Response(page(total=2)), Response(page('37291', total=2)),
            Response(text=detail()), Response(text=detail('90000', 'PAP')),
        ]) as fetch:
            path = Path(tmp) / 'rows.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['count'], 2)
            self.assertEqual(fetch.call_args_list[1].kwargs['data']['iDisplayStart'], 1)
            self.assertEqual(len(path.read_text().splitlines()), 2)

    def test_repeated_or_disappearing_page_fails_without_overwriting(self):
        for second in [page(total=2), {**page(total=2), 'aaData': []}, page('37291', total=3)]:
            adapter = CorteganaAyuntamientoAdapter('cortegana')
            with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_request', side_effect=[
                Response(page(total=2)), Response(second),
            ]):
                path = Path(tmp) / 'rows.jsonl'
                path.write_text('previous snapshot')
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_disabled_features_and_loadable_adapter(self):
        manifest = load_manifest('cortegana')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '21025')
        self.assertEqual(manifest.provincia, 'Huelva')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        from municipio.adapters.registry import load_portal_adapter
        self.assertIsInstance(load_portal_adapter(manifest), CorteganaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
