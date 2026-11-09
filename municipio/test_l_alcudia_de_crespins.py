"""Offline parser contract tests; run with python -m unittest municipio.test_l_alcudia_de_crespins."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.l_alcudia_de_crespins import (
    BASE, SOURCE, LAlcudiaDeCrespinsAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

TITLE = 'PGOU ( PLAN GENERAL DE ORDENACIÓN URBANÍSTICA)'
URL = BASE + '/plan-urbanistico/pgou/'


def inventory(total=1, pages=1):
    settings = {'preload_data': {'settings': {'pager': {
        'page': 1, 'total_pages': pages, 'total_rows': total, 'total_rows_unfiltered': total}}}}
    return '''<div class="facetwp-template" data-name="planes_urbansticos">
    <div class="fwpl-result"><div class="fwpl-item el-58pul">%s</div>
    <div class="fwpl-item el-o1n97f">2023</div><a href="%s">VER PLAN</a></div></div>
    <script>window.FWP_JSON = %s;</script>''' % (TITLE, URL, json.dumps(settings))


def detail():
    return '''<div data-elementor-type="single-page" class="plan-urbanistico">
    <h2>%s</h2><h2>Año: 2023</h2>
    <div class="e-con-inner"><a href="https://www.lalcudiadecrespins.es/PGOU2023.rar">DESCARGA PLAN COMPLETO</a></div>
    <div class="e-con-inner"><div class="elementor-widget-text-editor">CERTIFICADO PLENO 26/05/2023</div>
    <a href="/wp-content/uploads/2024/10/certificado.pdf">VER O DESCARGAR</a></div>
    <div class="e-con-inner"><div class="elementor-widget-text-editor">NORMAS</div>
    <a href="/wp-content/uploads/2024/10/NORMAS.zip">VER O DESCARGAR</a>
    <a href="/wp-content/uploads/2024/10/NORMAS.zip">Duplicado</a></div>
    <a role="button">VER O DESCARGAR</a></div>''' % TITLE


class ParserTests(unittest.TestCase):
    def test_grouping_provenance_and_date_semantics(self):
        row = parse_detail(detail(), parse_inventory(inventory())[0])
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['titulo'], 'CERTIFICADO PLENO 26/05/2023')
        self.assertEqual(row['documentos'][1]['source_url'], URL)
        self.assertEqual(row['source_url'], SOURCE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertEqual(row['anio_fuente'], '2023')
        self.assertEqual(row['codigo_ine'], '46020')

    def test_reject_incomplete_inventory(self):
        for html in (inventory(2, 2), inventory(2, 1), inventory().replace('window.FWP_JSON', 'missing')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_nav_and_application_forms_are_not_records(self):
        with self.assertRaises(ValueError):
            parse_inventory('<nav><a href="%s">PGOU</a></nav>' % URL)
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace(TITLE, 'Solicitud licencia de obras'))

    def test_changed_detail_or_missing_documents_fails(self):
        item = parse_inventory(inventory())[0]
        for html in (detail().replace(TITLE, 'Otro plan'), '<div>PGOU</div>',
                     '<div data-elementor-type="single-page" class="plan-urbanistico"><h2>%s</h2></div>' % TITLE):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, item)

    def test_unreviewed_links_fail(self):
        with self.assertRaises(ValueError):
            parse_detail(detail().replace('www.lalcudiadecrespins.es', 'example.org'), parse_inventory(inventory())[0])

    def test_snapshot_and_failure_preserves_previous_output(self):
        adapter = LAlcudiaDeCrespinsAyuntamientoAdapter('l-alcudia-de-crespins')
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail()]):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
            before = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory(), '<html>broken</html>']):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(d) / 'state.json')
            self.assertEqual(before, output.read_bytes())

    def test_manifest_and_registry(self):
        manifest = load_manifest('l-alcudia-de-crespins')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46020')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), LAlcudiaDeCrespinsAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
