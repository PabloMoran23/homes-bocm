import tempfile
import unittest
from pathlib import Path

from municipio.adapters.sopela import SopelaAyuntamientoAdapter as Adapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    links = [
        ('INFORME PREVIO', '/wp-content/uploads/2023/01/informe.pdf'),
        ('SÍNTESIS DEL DOCUMENTO DE INFORMACIÓN Y DIAGNÓSTICO', '/wp-content/uploads/2024/01/diagnostico.pdf'),
        ('CRITERIOS Y OBJETIVOS', '/wp-content/uploads/2025/03/criterios.pdf'),
        ('AVANCE + DOCUMENTO INICIAL ESTRATÉGICO', 'https://www.dropbox.com/scl/fo/abc/test?dl=0'),
        ('CUESTIONARIO ONLINE', 'https://forms.gle/abc'),
    ]
    anchors = ''.join(f'<a class="qbutton" href="{url}">{title}</a>' for title, url in links)
    return '<div class="content_inner">REVISIÓN DEL PGOU Sopela Documentos y formularios' + anchors * 2 + '</div>'


class SopelaTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = Adapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['codigo_ine'], '48085')
        self.assertTrue(all(d['source_url'] == Adapter.SOURCE for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon', 'fase'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], Adapter.parse_projects(fixture().replace('2025/03', '2026/01'))[0]['id'])

    def test_missing_documents_or_pagination_fail(self):
        for html in ('<h1>Sopela</h1>', fixture().replace('CRITERIOS Y OBJETIVOS', 'Futuro'),
                     fixture() + '<a rel="next" href="/es/page/2">2</a>',
                     fixture() + '<a href="/es/page/2">Siguiente</a>'):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('sopela')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '48085')
        self.assertEqual(raw['provincia'], 'Bizkaia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
