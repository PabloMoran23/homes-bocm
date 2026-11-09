"""Offline parser and adapter contract tests; no network required."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.bergondo import BergondoAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<h1>Borrador do PXOM</h1><article><div class="entry">' + body + '</div></article>'


class BergondoTests(unittest.TestCase):
    def test_amendments_group_documents_and_dates(self):
        html = page('''<p><strong>Aprobación DEFINITIVA da Modificación puntual sexta</strong></p>
        <p>Precisión de condicións de ordenación</p>
        <p>Aprobada defintivamente por orde da Conselleria o 22 de decembro de 2021
        (DOG do 13 de xaneiro de 2022). VIGOR: dende o 21 de xuño de 2022.</p>
        <p><a href="/six.pdf">Expediente</a><a href="/six.pdf">Duplicado</a></p>
        <p><a href="/initial.pdf">Aprobación inicial</a></p><hr>
        <p><strong>Aprobación inicial da Modificación puntual oitava</strong></p>
        <p>Núcleo de Gandarío</p><p><a href="/eight1.pdf">parte 1</a></p>
        <p><a href="/eight2.pdf">parte 2</a></p>''')
        rows = parse_inventory(html, 'https://bergondo.gal/inventory/', 'amendments')
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(rows[0]['fecha_acuerdo'], '2021-12-22')
        self.assertEqual(rows[0]['fase'], 'aprobación definitiva')
        self.assertEqual(rows[1]['fase'], 'aprobación inicial')
        self.assertIn('Gandarío', rows[1]['descripcion'])
        for key in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon']:
            self.assertNotIn(key, rows[0])
        self.assertNotIn('fecha_acuerdo', rows[1])

    def test_draft_is_one_instrument_not_per_plan_sheet(self):
        html = '<nav><a href="/unrelated.pdf">News</a></nav>' + page(
            '<p>Consulta o borrador</p><ul><li><a href="/mem.pdf">Memoria</a></li>'
            '<li><a href="/sheet.pdf">Babío</a></li></ul>')
        row, = parse_inventory(html, 'https://bergondo.gal/draft/', 'draft')
        self.assertEqual(row['fase'], 'borrador')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '15008')
        self.assertFalse(row['publication_ready'])

    def test_special_agreement_not_submission(self):
        row, = parse_inventory(page('''<p>PLAN ESPECIAL SENDA FLUVIAL DO RIO MAIOR</p>
        <p>APROBACIÓN DEFINITIVA</p><p>EXP: 2019/U035/000002</p>
        <p>O Pleno en sesión extraordinaria que tivo lugar o xoves 30 de outubro de 2025,
        adoptou o acordo; presentado o 17 de outubro de 2025.</p>
        <p><a href="https://sede.bergondo.gal/a.zip">Documento íntegro</a></p>'''),
                                 'https://bergondo.gal/special/', 'special')
        self.assertEqual(row['fecha_acuerdo'], '2025-10-30')
        self.assertEqual(row['expediente'], '2019/U035/000002')

    def test_physical_project_grouping(self):
        rows = parse_inventory(page('''<dl><dt>Rotonda Santa Marta de Babío</dt></dl>
        <p>Aprobación inicial</p><p><a href="/project.pdf">Proxecto técnico</a></p>
        <p><a href="/announcement.pdf">Anuncios BOP</a></p>
        <dl><dt>Outra rotonda</dt></dl><p><a href="/two.pdf">Proxecto</a></p>'''),
                               'https://bergondo.gal/works/', 'works')
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['tipo'], 'proyecto de urbanización')
        self.assertNotIn('fecha_acuerdo', rows[0])

    def test_changed_or_paginated_inventory_fails(self):
        valid = '<dl><dt>Rotonda</dt></dl><p><a href="/a.pdf">Memoria</a></p>'
        self.assertEqual(len(parse_inventory(page(valid), 'https://bergondo.gal/test/', 'works')), 1)
        for html in ['<html>Blocked</html>', page('<p>Formulario licencia</p>'),
                     page(valid + '<a href="?page=2" rel="next">2</a>'),
                     page(valid + '<div class="pagination"><a href="?page=2">2</a></div>'),
                     page(valid + '<a href="?page=2">Seguinte</a>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, 'https://bergondo.gal/test/', 'works')
        with self.assertRaises(ValueError):
            parse_inventory(page('<p>PLAN ESPECIAL SEN DOCUMENTOS</p>'),
                            'https://bergondo.gal/test/', 'special')

    def test_manifest_and_failed_fetch_preserve_output(self):
        manifest = load_manifest('bergondo')
        self.assertIsInstance(load_portal_adapter(manifest), BergondoAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'out.jsonl'
            out.write_text('previous\n')
            adapter = BergondoAyuntamientoAdapter('bergondo')
            with patch('municipio.adapters.bergondo.requests.get', side_effect=RuntimeError('failed')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['count'], 0)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
