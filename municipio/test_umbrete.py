"""Offline structural parser tests; no network or evidence directory required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.umbrete import SOURCES, UmbreteAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def doc(name, label='Documento técnico'):
    return ('<div class="media"><h4 class="title-element"><a href="/export/sites/'
            'umbrete/es/transparencia/.galleries/IND-53-/' + name + '.pdf">'
            + label + '</a></h4><p>Publicado BOP 04/12/2025</p></div>')


def page(body):
    return '<article class="sg-indicador-trans">' + body + '</article>'


class UmbreteTests(unittest.TestCase):
    def parse(self, body, indicator='53'):
        return parse_inventory(page(body), SOURCES[indicator], indicator)

    def test_grouping_and_no_document_leakage(self):
        rows, omitted = self.parse(
            '<h3>MODIFICACIONES DE LAS NNSS APROBADAS.</h3>'
            '<h4 class="gallery-title">EXPTE. 2011/01. MODIFICACIÓN ARTÍCULO 63</h4>'
            + doc('a') + doc('b', 'Acuerdo Pleno 27/11/2025') + doc('a')
            + '<h4 class="gallery-title">EXPTE. 2012/01. MODIFICACIÓN sin documentos</h4>'
            + '<h4 class="gallery-title">EXPTE. 2013/01. ESTUDIO DE DETALLE</h4>' + doc('c'))
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(len(omitted), 1)
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('/c.pdf'))
        self.assertIn('Publicado BOP', rows[0]['documentos'][0]['texto_fuente'])
        for row in rows:
            self.assertFalse(any(k in row for k in ('fecha', 'fecha_aprob', 'fecha_acuerdo',
                                                   'fecha_publicacion', 'lat', 'lon', 'fase')))
            self.assertEqual(row['codigo_ine'], '41094')
            self.assertFalse(row['publication_ready'])

    def test_pgom_single_instrument_across_galleries(self):
        rows, _ = self.parse('<h3>PLAN GENERAL DE ORDENACIÓN MUNICIPAL (PGOM).</h3>'
                             '<h4 class="gallery-title">MEMORIA</h4>' + doc('a')
                             + '<h4 class="gallery-title">PLANOS</h4>' + doc('b'), '50')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_housing_deduplicates_documents(self):
        rows, _ = self.parse('<h3>PLAN MUNICIPAL DE VIVIENDA Y SUELO</h3>'
                             '<h4 class="gallery-title">EXPTE. 2025/PES_02/002522</h4>'
                             + doc('a') + doc('a'), '55')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(rows[0]['expediente'], '2025/PES_02/002522')

    def test_pagination_fails(self):
        for link in ('<a rel="next" href="?page=2">2</a>',
                     '<a href="?page=2">Siguiente</a>',
                     '<ul class="pagination"><li><a href="?page=2">2</a></li></ul>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                self.parse('<h3>PLAN MUNICIPAL DE VIVIENDA Y SUELO</h3>' + doc('a') + link)

    def test_empty_forms_and_procurement_are_not_instruments(self):
        for body in ('', '<a href="/formulario.pdf">Solicitud licencia</a>',
                     '<h3>Anuncio de licitación</h3>' + doc('a')):
            with self.assertRaises(ValueError):
                self.parse(body)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            parse_inventory('<html>Error</html>', SOURCES['53'], '53')

    def test_external_document_rejected(self):
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.parse('<h3>PLAN MUNICIPAL DE VIVIENDA Y SUELO</h3>'
                       '<a href="https://example.com/a.pdf">Other</a>')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('umbrete')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(NotImplementedError):
            UmbreteAyuntamientoAdapter('umbrete').backfill_licencias(Path('unused'))

    def test_fetch_failure_does_not_replace_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'records.jsonl'
            path.write_text('previous')
            with patch('municipio.adapters.umbrete.requests.get', side_effect=RuntimeError('network')):
                with self.assertRaises(RuntimeError):
                    UmbreteAyuntamientoAdapter('umbrete').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous')


if __name__ == '__main__':
    unittest.main()
