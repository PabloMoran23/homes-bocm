import tempfile
import unittest
from pathlib import Path

from municipio.adapters.los_silos import (
    SOURCE, LosSilosAyuntamientoAdapter, extract_inventory, parse_sections,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def section(title, body):
    return ('<div class="et_pb_accordion_item"><h5 class="et_pb_toggle_title">'
            + title + '</h5><div class="et_pb_toggle_content">' + body + '</div></div>')


class LosSilosTests(unittest.TestCase):
    def test_grouping_children_provenance_and_dates(self):
        root = section('Plan General de Ordenación vigente',
                       '<a href="/pgo.pdf">Memoria</a><a href="/child/">Planos</a>')
        root += section('Plan Especial de Protección del Casco Historico',
                        '<a href="/pep.pdf">Normas</a>')
        child = section('Erjos', '<a href="/pgo.pdf">Duplicado</a><a href="/map.pdf"><img></a>'
                                '<a href="/download.png"><img></a><a href="/child/">Ciclo</a>')
        calls = []
        def fetch(url):
            calls.append(url)
            return {SOURCE: root, 'https://www.lossilos.es/child/': child}[url]
        rows = extract_inventory(fetch)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[0]['documentos'][0]['procedencia']), 2)
        self.assertEqual(rows[0]['documentos'][1]['titulo'], 'Erjos')
        self.assertEqual(len(rows[0]['incidencias_fuente']), 1)
        self.assertEqual(calls, [SOURCE, 'https://www.lossilos.es/child/'])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '38042')
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon'):
                self.assertNotIn(key, row)

    def test_fail_closed(self):
        good = section('Plan General', '<a href="/pgo.pdf">Memoria</a>')
        for html in ('<html>Unavailable</html>', good + '<a rel="next" href="/page/2">2</a>',
                     good + '<a href="/page/2">Siguiente</a>',
                     section('Plan General', '<a href="https://example.org/x.pdf">x</a>'),
                     section('Plan General', '<a href="/new.zip">x</a>'),
                     section('Plan General', 'Sin documentos')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_sections(html, SOURCE)
        with self.assertRaises(ValueError):
            extract_inventory(lambda url: section('Plan General', '<a href="/icon.png">x</a>'))

    def test_failed_child_preserves_existing_output(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text('previous\n')
            with patch('municipio.adapters.los_silos.extract_inventory', side_effect=ValueError('missing child')):
                with self.assertRaises(ValueError):
                    LosSilosAyuntamientoAdapter('los-silos').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('los-silos')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, LosSilosAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
