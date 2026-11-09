import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from municipio.adapters.olite import SOURCE, OliteAyuntamientoAdapter, parse_dossier, parse_page
from municipio.manifest import load_manifest


def page(title, body, published=''):
    return (f'<div class="cabecera-single"><h2 class="titulo-single">{title}</h2>{published}</div>'
            f'<div class="contenido content"><div class="mt-3">{body}</div></div>')


class OliteTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        root = page('Plan General Municipal', 'EMOT <a href="/emot/">Documentación</a>'
                    '<a href="/emot/">Duplicado</a>')
        child = page('EMOT', 'Versión preliminar <a href="https://drive.google.com/file/d/abc/view?usp=x">Memoria</a>'
                     '<a href="https://drive.google.com/file/d/abc/view">Memoria duplicada</a>'
                     '<a href="https://forms.gle/example">Encuesta</a>',
                     '<div class="noticia_fecha">24 de mayo de 2024</div>')
        fetch = Mock(return_value=child)
        rows = parse_dossier(root, fetch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(rows[0]['paginas_fuente'][1]['fecha_publicacion'], '2024-05-24')
        self.assertNotIn('fecha_acuerdo', rows[0])
        self.assertNotIn('fecha_publicacion', rows[0])
        self.assertNotIn('lat', rows[0])
        fetch.assert_called_once_with('https://www.olite.es/emot/')

    def test_sidebar_not_scraped(self):
        html = page('Plan General Municipal', 'EMOT') + '<aside><a href="/news/">Noticia</a></aside>'
        self.assertEqual(parse_page(html, SOURCE)[2], [])

    def test_fail_on_pagination_missing_content_or_documents(self):
        for html in [page('Plan General Municipal', 'EMOT <a rel="next" href="/p2/">2</a>'),
                     page('Plan General Municipal', 'EMOT <a href="/p2/">Siguiente</a>'),
                     '<h1>Unavailable</h1>', page('Plan General Municipal', 'EMOT')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_dossier(html, Mock())

    def test_manifest_disabled_licences_and_failed_fetch_preserves_output(self):
        manifest = load_manifest('olite')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.olite:OliteAyuntamientoAdapter')
        self.assertFalse(manifest.licencias.enabled)
        adapter = OliteAyuntamientoAdapter('olite')
        with TemporaryDirectory() as directory:
            out = Path(directory) / 'rows.jsonl'
            out.write_text('previous\n')
            with patch('municipio.adapters.olite.requests.Session') as session:
                session.return_value.__enter__.return_value.get.side_effect = RuntimeError('network')
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
