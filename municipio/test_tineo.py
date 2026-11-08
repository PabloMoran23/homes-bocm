import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.tineo import SOURCE, TineoAyuntamientoAdapter
from municipio.manifest import load_manifest


def doc(name, title):
    return f'<li><a href="/documents/176602/1/{name}.pdf/{name}?t=123">{title}</a></li>'


def page(body):
    return ('<div class="journal-content-article"><div class="titulo">'
            '<h2>Instrumentos urbanísticos en tramitación</h2></div>'
            f'<div class="detalle">{body}</div></div>')


FIXTURE = page(
    '<p>UNIDAD DE ACTUACIÓN “CAMINO DE SAN ROQUE”-TINEO</p><ul>'
    + doc('a', 'Anuncio de aprobación inicial') + doc('b', 'Proyecto diligenciado') + '</ul>'
    '<p>PROYECTO DE DELIMITACIÓN DE UNIDAD DE ACTUACIÓN EN NAVELGAS</p><ul>'
    + doc('c', 'Anuncio de aprobación inicial') + doc('d', 'Proyecto diligenciado') + '</ul>'
    '<p>ALISEDA S.A.U. : DELIMITACIÓN de UNIDAD DE ACTUACIÓN</p><ul>'
    + doc('e', 'Resolución por la que se aprueba inicialmente') + doc('f', 'Solicitud ALISEDA')
    + doc('g', 'DOCUMENTO DE APROBACIÓN INICIAL. VENTA QUILDÁN (TINEO). DICIEMBRE 2021') + '</ul>'
    '<p>APROBACIÓN INICIAL DEL DOCUMENTO DE MODIFICACIÓN DEL PLAN GENERAL DE ORDENACIÓN URBANA DE TINEO</p><ul>'
    + doc('h', 'Documento de anuncio de aprobación inicial') + doc('i', 'Propuesta de modificación puntual') + '</ul>'
)


class TineoTests(unittest.TestCase):
    def test_instruments_and_provenance(self):
        rows = TineoAyuntamientoAdapter.parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 5)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2, 1, 2])
        self.assertEqual(rows[3]['tipo'], 'modificacion_pgou')
        self.assertEqual(rows[3]['fase'], 'documento de aprobación inicial')
        self.assertNotIn('VENTA', str(rows[2]['documentos']))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '33073')
            self.assertIn(row['fase'], {'aprobación inicial', 'documento de aprobación inicial'})
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['lat'])
            self.assertEqual(row['documentos'][0]['origen_url'], SOURCE)
        refreshed = TineoAyuntamientoAdapter.parse_inventory(FIXTURE.replace('t=123', 't=999'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in refreshed])

    def test_duplicate_attachments(self):
        html = FIXTURE.replace(doc('b', 'Proyecto diligenciado'), doc('b', 'Proyecto diligenciado') * 2)
        self.assertEqual(len(TineoAyuntamientoAdapter.parse_inventory(html)[0]['documentos']), 2)

    def test_fail_closed(self):
        for html in ['', page(''), page('<p>Formulario de licencia</p>'),
                     FIXTURE + '<a rel="next" href="?page=2">2</a>',
                     FIXTURE + '<a href="/page2">Siguiente</a>',
                     FIXTURE.replace('/documents/176602/1/a.pdf/a', 'https://example.org/a'),
                     page('<p>UNIDAD DE ACTUACIÓN SIN DOCUMENTOS</p>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                TineoAyuntamientoAdapter.parse_inventory(html)

    def test_live_method_contract_and_disabled_licences(self):
        response = Mock(text=FIXTURE, url=SOURCE)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.tineo.requests.get', return_value=response):
            adapter = TineoAyuntamientoAdapter()
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['rows'], 5)
            before = out.read_text()
            response.text = 'broken'
            with self.assertRaises(ValueError):
                adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['rows'], 0)
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('tineo')
        self.assertEqual(manifest.provincia, 'Asturias')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
