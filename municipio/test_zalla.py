import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.zalla import SOURCE, ZallaAyuntamientoAdapter
from municipio.manifest import load_manifest


def fixture():
    docs = [('AVANCE: MEMORIA', '/wp-content/uploads/2024/05/memoria.pdf'),
            ('AVANCE: DOCUMENTO INICIAL ESTRATÉGICO', '/wp-content/uploads/2024/05/die.pdf'),
            ('AVANCE: PLANOS', 'https://www.dropbox.com/scl/fo/planos?rlkey=abc&dl=0'),
            ('INFORME DE PARTICIPACIÓN', '/wp-content/uploads/2024/09/informe.pdf'),
            ('CUESTIONARIO', 'https://forms.gle/example')]
    links = ''.join(f'<a href="{url}">{title}</a>' for title, url in docs)
    return ('<h2>Nuevo PGOU de Zalla</h2><p>FASE 9 Aprobación Definitiva 2024</p>'
            '<div><h2>Documentos</h2>' + links + links + '</div>'
            '<footer><a href="/wp-content/uploads/2024/05/ajeno.pdf">Ajeno</a></footer>')


class ZallaTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = ZallaAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '48096')
        self.assertEqual(len(row['documentos']), 4)
        self.assertTrue(any('rlkey=abc&dl=0' in d['url'] for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_fail_closed(self):
        for html in ('<h2>Licencia de obras</h2>', fixture().replace('AVANCE: MEMORIA', 'Otro'),
                     fixture() + '<a rel="next" href="?page=2">2</a>',
                     fixture() + '<a href="?page=2">Siguiente</a>',
                     fixture().replace('https://forms.gle/example', 'https://example.org/unknown')):
            with self.subTest(html=html[-90:]), self.assertRaises(ValueError):
                ZallaAyuntamientoAdapter.parse_projects(html)

    def test_adapter_and_disabled_licences(self):
        manifest = load_manifest('zalla')
        self.assertFalse(manifest.licencias.enabled)
        adapter = ZallaAyuntamientoAdapter('zalla')
        response = Mock(url=SOURCE, text=fixture(), content=fixture().encode())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.zalla.requests.get', return_value=response):
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json')['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'zalla-proy-pgou')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        response.raise_for_status.assert_called_once()


if __name__ == '__main__':
    unittest.main()
