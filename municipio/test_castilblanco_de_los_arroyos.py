"""Parser and snapshot regression checks; fixtures model official OpenCMS markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.castilblanco_de_los_arroyos import (
    SOURCES, CastilblancoDeLosArroyosAyuntamientoAdapter, build_records, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def link(name, path):
    return f'<a href="/export/{path}.pdf">{name}</a>'


def fixtures():
    return {
        'consulta': '<h1>Nuevo Plan Básico de Ordenación Municipal</h1><table class="table">'
                    + link('Consulta pública PBOM', 'consulta') + '</table>',
        'avance': '<article class="sg-indicador-trans"><h2 class="title">Avance del Plan Basico de Ordenación Municipal.</h2>'
                  '<div class="contentblock">' + link('Memoria', 'memoria') + link('Plano', 'plano') + '</div>'
                  '<div class="contentblock">' + link('R.A. aprobación avance', 'resolucion') + '</div></article>',
        'pgou': '<article class="sg-indicador-trans"><h2 class="title">Plan General de Ordenación Urbana</h2>'
                '<section class="gallery"><h4 class="gallery-title">ADAPTACION PARCIAL A LA LOUA DE NORMAS SUBSIDIARIAS</h4>'
                + link('Memoria justificativa', 'adaptacion') + link('Memoria duplicada', 'adaptacion')
                + link('BOP TASAS VEHICULOS PRECIOS PISCINA', 'tasas') + '</section>'
                '<section class="gallery"><h4 class="gallery-title">Propuesta Final Del Plan Modificación nº1 Del PGOU-Adp Para Ampliación Del Cementerio</h4>'
                + link('Aprobación definitiva Modif-1', 'cementerio') + '</section></article>',
    }


class CastilblancoTests(unittest.TestCase):
    def test_grouping_provenance_and_no_inferred_dates(self):
        rows = build_records(fixtures())
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]['documentos']), 4)
        self.assertEqual(rows[0]['source_urls'], [SOURCES['consulta'], SOURCES['avance']])
        self.assertEqual([len(r['documentos']) for r in rows[1:]], [1, 1])
        self.assertTrue(rows[2]['documentos'][0]['url'].endswith('/cementerio.pdf'))
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('/adaptacion.pdf'))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '41027')
            self.assertEqual(row['provincia'], 'Sevilla')
            for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertNotIn('fase', row)
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(d['source_url'] in row['source_urls'] for d in row['documentos']))

    def test_navigation_forms_and_unrelated_news_are_not_instruments(self):
        for kind in SOURCES:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                parse_inventory('<nav>' + link('PGOU', 'pgou') + '</nav><p>Noticias</p>', kind)
        data = fixtures()
        data['consulta'] = data['consulta'].replace('Consulta pública PBOM', 'MODELO DE SOLICITUD')
        with self.assertRaises(ValueError):
            build_records(data)

    def test_pagination_and_hidden_collector_truncation_raise(self):
        html = fixtures()['avance']
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(html + '<ul class="pagination"><li><a href="?page=2">2</a></li></ul>', 'avance')
        with self.assertRaisesRegex(ValueError, 'collector'):
            parse_inventory(html + '<div class="sg-download-gallery"><table><tbody><tr><td>x</td></tr></tbody></table><!-- collectorParam: rows=1 - resultSize: 2 --></div>', 'avance')

    def test_changed_gallery_and_external_document_raise(self):
        html = fixtures()['pgou'].replace('ADAPTACION PARCIAL A LA LOUA DE NORMAS SUBSIDIARIAS', 'Nuevo plan desconocido')
        with self.assertRaises(ValueError):
            parse_inventory(html, 'pgou')
        html = fixtures()['consulta'].replace('/export/consulta.pdf', 'https://example.org/file.pdf')
        with self.assertRaises(ValueError):
            parse_inventory(html, 'consulta')

    def test_live_methods_use_parser_and_replace_snapshot(self):
        data = fixtures()
        def get(url, **kwargs):
            kind = next(k for k, value in SOURCES.items() if value == url)
            class Response:
                headers = {'Content-Type': 'text/html; charset=utf-8'}
                text = data[kind]
                content = text.encode()
                def raise_for_status(self):
                    pass
            result = Response()
            result.url = url
            return result
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.castilblanco_de_los_arroyos.requests.get', side_effect=get):
            adapter = CastilblancoDeLosArroyosAyuntamientoAdapter('castilblanco-de-los-arroyos')
            out = Path(tmp) / 'projects.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['count'], 3)
            before = out.read_text()
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), before)
            data['avance'] = '<h1>Unavailable</h1>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), before)
            lic = Path(tmp) / 'lic.jsonl'
            self.assertTrue(adapter.backfill_licencias(lic)['disabled'])
            self.assertEqual(lic.read_text(), '')

    def test_manifest_and_dynamic_adapter_loading(self):
        manifest = load_manifest('castilblanco-de-los-arroyos')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CastilblancoDeLosArroyosAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
