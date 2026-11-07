import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.l_escala import LEscalaAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def doc(name, label):
    return f'<a href="/documents/2475467/5063793/{name}">{label}</a>'


def page(items):
    return '<div class="journal-content-article"><ul>' + items + '</ul></div>Actualització: 28/09/2026'


class LEscalaTests(unittest.TestCase):
    def test_group_nested_documents_and_estany_parts(self):
        html = page('<li>Modificació del PGOU hotelers<ul><li>' + doc('a', 'PGOU') +
                    '</li><li>' + doc('b', 'Ambiental') + '</li></ul></li>' +
                    '<li>' + doc('c', 'MP_PGOU_Estany_Poma_plànols') + '</li><li>' +
                    doc('d', 'MP_PGOU_Estany_Poma_memòria') + '</li>')
        rows = LEscalaAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '17062')
            self.assertEqual(row['fecha_actualizacion_fuente'], '2026-09-28')
            for field in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertIsNone(row[field])

    def test_duplicate_and_invalid_link_provenance(self):
        rows = LEscalaAyuntamientoAdapter.parse_projects(page(
            '<li>Modificació del PGOU hotelers<ul><li>' + doc('a', 'PGOU') +
            doc('a', '') + '<a href="http://Estudi mobilitat">Mobilitat</a></li></ul></li>'))
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(rows[0]['enlaces_no_documentales'][0]['url_original'], 'http://Estudi mobilitat')

    def test_reject_empty_unknown_and_pagination(self):
        valid = page('<li>' + doc('a', 'PLA PARCIAL URBANÍSTIC HORTA') + '</li>')
        for html in ['<html>Login</html>', page('<li>'+doc('a', 'Sol·licitud llicència')+'</li>'),
                     valid + '<a rel="next" href="?page=2">2</a>',
                     valid + '<a href="?page=2">Següent</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                LEscalaAyuntamientoAdapter.parse_projects(html)

    def test_manifest_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('l-escala'))
        self.assertIsInstance(adapter, LEscalaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            with patch('municipio.adapters.l_escala.requests.get', side_effect=AssertionError('Network forbidden')):
                self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
