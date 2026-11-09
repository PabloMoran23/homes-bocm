import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.san_vicente_de_la_barquera import (
    SOURCE, SanVicenteDeLaBarqueraAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def section(title, content):
    return (f'<div class="elementor-toggle-item"><div class="elementor-tab-title">{title}</div>'
            f'<div class="elementor-tab-content">{content}</div></div>')


def link(label, path='/file/test.pdf'):
    return f'<a href="{path}">{label}</a>'


PGOU = section('PGOU San Vicente 2015',
               'Aprobación CROTU: 21/05/2015 | Publicación BOC: 19/08/2015 ' + link('Memoria'))


class ParserTests(unittest.TestCase):
    def test_grouping_nested_documents_and_distinct_dates(self):
        nested = section('Ordenación', link('Plano', '/file/plano.pdf'))
        html = section('PGOU San Vicente 2015',
                       'Aprobación CROTU: 21/05/2015 | Publicación BOC: 19/08/2015 ' +
                       link('Memoria') + link('Duplicado') + nested)
        html += section('Criterios de Interpretación. PGOU', link('Publicación BOC', '/file/criterios.PDF'))
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['fecha_acuerdo'], '2015-05-21')
        self.assertEqual(row['fecha_publicacion'], '2015-08-19')
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos_complementarios']), 1)
        self.assertEqual(row['documentos'][1]['url'], 'https://aytosanvicentedelabarquera.es/file/plano.pdf')

    def test_stages_dates_and_identity_do_not_come_from_upload_paths(self):
        initial = section('Expediente 840/2025. Estudio de detalle en Paseo de la Barquera 22 y 61',
                          link('Anuncio BOC aprob. inicial', '/wp-content/uploads/2026/02/2026-668.pdf'))
        definitive = initial.replace('aprob. inicial', 'aprobación definitiva')
        first = Adapter.parse_projects(PGOU + initial)[1]
        second = Adapter.parse_projects(PGOU + definitive)[1]
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['fase'], 'aprobación inicial')
        self.assertEqual(second['fase'], 'aprobación definitiva')
        self.assertIsNone(first['fecha_publicacion'])
        self.assertIsNone(first['fecha_acuerdo'])
        self.assertIsNone(first['lat'])
        self.assertIsNone(first['geometry'])

    def test_truncated_date_and_catalogue_title_dates(self):
        special = section('Plan Especial de Protección Y Reforma Interior del Casco Antiguo de la Villa',
                          'Aprobación CROTU: 24/02/1993 | Publicación BOC: 19/07/1 ' + link('Memoria'))
        catalogue = section('Catálogo de edificaciones en suelo rústico (C.E.S.R) - Aprobado en el pleno extraordinario del 20 de Junio de 2013, publicado BOC del 17 de Julio de 2013', link('Ficha'))
        rows = Adapter.parse_projects(PGOU + special + catalogue)
        self.assertEqual(rows[1]['fecha_acuerdo'], '1993-02-24')
        self.assertIsNone(rows[1]['fecha_publicacion'])
        self.assertEqual(rows[2]['fecha_acuerdo'], '2013-06-20')
        self.assertEqual(rows[2]['fecha_publicacion'], '2013-07-17')

    def test_rejects_empty_changed_paginated_and_ambiguous_sources(self):
        invalid = [link('Urbanismo'), '<form>Solicitud de licencia</form>',
                   PGOU + '<a rel="next" href="?page=2">2</a>',
                   PGOU + '<a href="?page=2">Siguiente</a>',
                   PGOU + PGOU, PGOU + section('Proyecto nuevo sin revisar', link('PDF')),
                   section('PGOU San Vicente 2015', ''),
                   section('PGOU San Vicente 2015', link('Login', '/login'))]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_exclusions_and_unknown_stage(self):
        html = PGOU + section('Expediente 1648/2018: constitución Junta de compensación', link('Estatutos'))
        html += section('Plan de Ordenación de los Recursos Naturales del Parque Natural de Oyambre', link('Decreto'))
        html += section('Estudio de detalle en Barrio Oyambre', link('PLANOS'))
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[1]['fase'])

    def test_manifest_loading_refresh_and_disabled_licences(self):
        manifest = load_manifest('san-vicente-de-la-barquera')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        response = Mock(text=PGOU)
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.san_vicente_de_la_barquera.requests.get', return_value=response) as get:
            path = Path(tmp) / 'proyectos.jsonl'
            adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '39080')
            self.assertEqual(get.call_args.args[0], SOURCE)
            result = adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual(result['rows'], 0)
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
