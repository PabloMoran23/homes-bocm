"""Offline parser regressions; fixtures represent municipal inventory structure."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.zuera import SOURCE, ZueraAyuntamientoAdapter
from municipio.manifest import load_manifest


def doc(name, label=None):
    return f'<a href="/wp-content/uploads/2024/01/{name}.pdf">{label or name}</a>'


def inventory(body):
    return ('<main id="page-content"><h1>Planeamiento</h1>'
            '<h3>PLAN GENERAL DE ORDENACION URBANA<br>Texto refundido 2014</h3>'
            + doc('normas') + body + '<h2>Noticias Urbanismo</h2>'
            + doc('unrelated-news') + '</main>')


class ZueraTests(unittest.TestCase):
    def test_grouping_parentage_and_date_semantics(self):
        html = inventory(
            '<h2>Planos de Ordenación</h2><h3>Alineaciones</h3>' + doc('plano')
            + '<h2>Modificaciones Aisladas</h2>'
            '<p><strong>MODIFICACION AISLADA Nº5. SUPRESION ZUA2</strong></p><p>'
            + doc('acuerdo', 'ACUERDO de APROBACION DEFINITIVA CPUZ (18072021) MOD5')
            + doc('mod5') + doc('mod5') + '</p>'
            '<h3>Planeamiento de desarrollo</h3><h3>Planes Parciales</h3>'
            '<h2>Zuera Sur</h2><h4>Textos:</h4>' + doc('memoria')
            + '<h2>Modificaciones Aisladas – Plan Parcial Zuera Sur</h2>'
            '<p><strong>MODIFICACION AISLADA Nº6.</strong></p>' + doc('mod6')
            + '<h2>Plan de Movilidad Urbana Sostenible</h2>' + doc('pmus'))
        rows = ZueraAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows), 5)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1, 1, 1])
        self.assertEqual(rows[1]['instrumento_padre'], rows[0]['id'])
        self.assertEqual(rows[3]['instrumento_padre'], rows[2]['id'])
        for row in rows:
            for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertEqual(row['codigo_ine'], '50298')
            self.assertEqual(row['documentos'][0]['url_origen'], SOURCE)
        self.assertIn('(18072021)', rows[1]['documentos'][0]['titulo'])

    def test_stable_identity_when_documents_change(self):
        a = ZueraAyuntamientoAdapter.parse_projects(inventory(''))
        b = ZueraAyuntamientoAdapter.parse_projects(inventory(doc('new-edition')))
        self.assertEqual(a[0]['id'], b[0]['id'])

    def test_refuses_pagination(self):
        for pagination in ('<a rel="next" href="?page=2">2</a>',
                           '<a href="?page=2">Siguiente</a>', '<nav class="pagination">2</nav>'):
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                ZueraAyuntamientoAdapter.parse_projects(inventory(pagination))

    def test_refuses_unknown_document_context(self):
        with self.assertRaises(ValueError):
            ZueraAyuntamientoAdapter.parse_projects(inventory('<h2>Nuevo plan especial</h2>' + doc('new')))

    def test_refuses_login_empty_or_incomplete_sources(self):
        for html in ('<h1>Login</h1>', '<main id="page-content"><h1>Planeamiento</h1></main>',
                     inventory('').replace('<h2>Noticias Urbanismo</h2>', ''),
                     inventory('').replace(doc('normas'), '')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                ZueraAyuntamientoAdapter.parse_projects(html)

    def test_external_document_refused(self):
        with self.assertRaises(ValueError):
            ZueraAyuntamientoAdapter.parse_projects(inventory('<a href="https://example.org/plan.pdf">plan</a>'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('zuera')
        self.assertEqual(manifest.provincia, 'Zaragoza')
        self.assertFalse(manifest.licencias.enabled)
        adapter = ZueraAyuntamientoAdapter('zuera')
        with TemporaryDirectory() as directory, patch('requests.Session') as network:
            result = adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')
            self.assertEqual(result['status'], 'disabled')
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
