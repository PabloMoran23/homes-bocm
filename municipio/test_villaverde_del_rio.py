"""Offline parser and adapter contract tests; fixtures model the official gallery."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.villaverde_del_rio import (
    DOC_PATH, SOURCE, VillaverdeDelRioAyuntamientoAdapter, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def attachment(filename, title, date=''):
    time = f'<time datetime="{date}">fecha CMS</time>' if date else ''
    return (f'<div class="media"><div class="media-body"><h4>'
            f'<a href="{DOC_PATH}{filename}">{title}</a></h4>{time}</div></div>')


def fixture():
    return '''<article class="sg-indicador-trans">
    <p>El Planeamiento aprobado del Ayuntamiento de Villaverde del Río se compone de:</p>
    <p>- Las Normas subsidiarias aprobadas el 21/12/1993</p>
    <p>- La Adaptación Parcial de las Normas a la L.O.U.A. aprobadas el 26/04/2012</p>
    <p>El PGOU se encuentra en fase de Avance, aprobado por Pleno de 22/01/2015.</p>
    <section class="gallery">''' + ''.join([
        attachment('NNSS-Memoria.pdf', 'NNSS Memoria'),
        attachment('NNSS-Planos.-Territorio.pdf', 'NNSS Planos. Territorio'),
        attachment('AdaptacionVillaverde_V5.pdf', 'AdaptacionVillaverde_V5', '2015-12-02T12:13:00.000+0100'),
        attachment('Publicacion-en-el-BOP.pdf', 'Publicacion en el BOP', '2015-12-02T12:13:00.000+0100'),
        attachment('C1av_docINFORMACION_dic2014_p.pdf', 'Memoria información'),
        attachment('C1avI_p05_NNSubsidiarias_AdapLOUA_dic2014.pdf', 'NNSS adaptación (mapa del avance)'),
    ]) + '</section></article>'


class ParserTests(unittest.TestCase):
    def test_instruments_group_documents_and_preserve_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2])
        self.assertEqual([r['fecha_acuerdo'] for r in rows], ['1993-12-21', '2012-04-26', '2015-01-22'])
        self.assertTrue(rows[2]['documentos'][1]['url'].endswith('C1avI_p05_NNSubsidiarias_AdapLOUA_dic2014.pdf'))
        self.assertEqual(rows[2]['fase'], 'avance aprobado')
        self.assertEqual(rows[1]['documentos'][0]['fecha_publicacion'], '2015-12-02')
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertFalse(row['publication_ready'])
            self.assertNotIn('lat', row)
            self.assertNotIn('lon', row)
            self.assertNotIn('fecha_aprob', row)
            for doc in row['documentos']:
                self.assertEqual(doc['source_url'], SOURCE)

    def test_duplicate_documents_and_irrelevant_navigation(self):
        html = fixture().replace('</section>', attachment('NNSS-Memoria.pdf', 'duplicado') + '</section>')
        html += '<nav><a href="/licencia.pdf">Formulario de licencia</a></nav>'
        self.assertEqual(sum(len(r['documentos']) for r in parse_inventory(html)), 6)

    def test_does_not_synthesize_records_from_title_or_news(self):
        for html in ('', '<h1>PGOU Villaverde del Río</h1>',
                     '<article class="sg-indicador-trans"><p>Villaverde del Río: anuncio de licitación</p></article>',
                     fixture().replace('section class="gallery"', 'section class="changed"')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_never_silently_truncated(self):
        for marker in ('<a rel="next" href="?page=2">Siguiente</a>', '<ul class="pagination"></ul>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(fixture() + marker)

    def test_unknown_documents_and_foreign_origins_fail(self):
        for filename in ('Nuevo-plan.pdf',):
            with self.assertRaisesRegex(ValueError, 'Unclassified'):
                parse_inventory(fixture().replace('</section>', attachment(filename, 'Nuevo plan') + '</section>'))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            parse_inventory(fixture().replace(DOC_PATH + 'NNSS-Memoria.pdf', 'https://example.org/NNSS-Memoria.pdf'))

    def test_narrative_changes_and_invalid_dates_fail(self):
        for html in (fixture().replace('21/12/1993', '31/02/1993'),
                     fixture().replace('aprobado por Pleno', 'en redacción por Pleno')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_ids_do_not_depend_on_document_order(self):
        one = parse_inventory(fixture())
        two = parse_inventory(fixture().replace('</section>', attachment('NNSS-Otro.pdf', 'NNSS Otro') + '</section>'))
        self.assertEqual([r['id'] for r in one], [r['id'] for r in two])

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest('villaverde-del-rio')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE, text=fixture(), content=fixture().encode())
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.villaverde_del_rio.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'unused-state')
            self.assertEqual(result['count'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')

    def test_http_failure_does_not_replace_output(self):
        adapter = VillaverdeDelRioAyuntamientoAdapter('villaverde-del-rio')
        response = Mock(url=SOURCE)
        response.raise_for_status.side_effect = RuntimeError('HTTP failure')
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.villaverde_del_rio.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaisesRegex(RuntimeError, 'HTTP failure'):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
