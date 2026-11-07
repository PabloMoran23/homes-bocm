import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.mula import (
    INDEX, MODS, PGMO, MulaAyuntamientoAdapter, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def wrap(text):
    return '<div class="post-content">' + text + '</div>'


def panel(number):
    return f'''<div class="fusion-panel"><span class="fusion-toggle-heading">Modificación nº{number} del PGMO</span>
    <div class="panel-body"><a href="/web/proyecto-{number}.pdf">Proyecto</a>
    <a href="https://borm.es/services/anuncio/ano/2024/numero/{number}/pdf">Publicación BORM aprobación definitiva</a></div></div>'''


class MulaTests(unittest.TestCase):
    def test_grouping_and_stable_identity(self):
        rows = parse_page(wrap(panel(24) + panel(25)), MODS)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        changed = parse_page(wrap(panel(25) + panel(24)), MODS)
        self.assertEqual(rows[0]['id'], changed[1]['id'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['lat'])

    def test_pgmo_separates_special_and_document_dates(self):
        html = wrap('''<h2>PGMO actualmente en vigor</h2>
        <a href="/web/memoria.pdf">Memoria. Aprobado por el Pleno en sesión 28 de junio de 2012</a>
        <a href="/web/2014/rect.pdf">Rectificaciones. Aprobado por el Pleno en sesión 27 de noviembre de 2014</a>
        <h2>Normativa (Plan Especial de Protección)</h2><a href="/web/especial.pdf">Memoria especial</a>
        <h2>Estudios Previos</h2><a href="/web/1995/estudios.pdf">Estudios 1995</a>''')
        row, = parse_page(html, PGMO)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][0]['fecha_acuerdo'], '2012-06-28')
        self.assertEqual(row['documentos'][1]['fecha_acuerdo'], '2014-11-27')
        self.assertNotIn('fecha_acuerdo', row['documentos'][2])
        self.assertIsNone(row['fecha_aprob'])

    def test_reject_empty_pagination_duplicate_and_unknown_group(self):
        for html in ('Login', wrap('<a href="/form.pdf">Solicitud de licencia</a>'),
                     wrap(panel(24)) + '<a rel="next" href="/page/2">Next</a>',
                     wrap(panel(24) + panel(24)),
                     wrap('<div class="fusion-panel">Nuevo formato</div>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, MODS)

    def test_index_excludes_forms_and_duplicate_works(self):
        work = '<a href="https://drive.google.com/file/d/real/view">Proyecto obras de excavación y protección de acceso al Castillo de Mula</a>'
        row, = parse_page(wrap(work + work + '<a href="/licencia.pdf">Solicitud de licencia</a>'), INDEX)
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['tipo'], 'proyecto de obras')

    def test_failure_does_not_write_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'rows.jsonl'
            out.write_text('previous snapshot')
            response = Mock(url=INDEX, headers={'Content-Type': 'text/html'}, content=b'Login')
            with patch('municipio.adapters.mula.requests.get', return_value=response), self.assertRaises(ValueError):
                MulaAyuntamientoAdapter().backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('mula')
        self.assertEqual(manifest.provincia, 'Murcia')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '30029')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = MulaAyuntamientoAdapter().backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
