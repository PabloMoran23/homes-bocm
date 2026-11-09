import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sils import SilsAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def fixture(extra=''):
    return '''<article id="post-3217"><h1 class="entry-title">POUM</h1><div class="entry-content">
    <p>Consultar <a href="/formulari">formulari de llicències</a></p>
    <p><strong>Exposició modificació Pla Parcial sect</strong><strong>or Massabè</strong></p>
    <ul><li><a href="/plan.pdf">Memòria</a></li><li><a href="/annex.pdf">Annex</a></li>
    <li><a href="/acord.pdf">Text integre aprovació Inicial Acord de Ple 30/06/2021</a></li></ul>
    <p><strong>Podeu consultar el Pla Ordenació Urbanística Municipal a través del registre</strong></p>
    <ul><li><a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/257083">RPUC</a></li></ul>
    ''' + extra + '</div></article>'


class SilsTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        rows = Adapter.parse_projects(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertIn('sector Massabè', rows[0]['titulo'])
        self.assertEqual(rows[0]['fecha_acuerdo'], '2021-06-30')
        self.assertEqual(rows[0]['fase'], 'aprobación inicial')
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])
        self.assertIsNone(rows[1]['fase'])

    def test_missing_dates_stay_null(self):
        html = fixture().replace('Text integre aprovació Inicial Acord de Ple 30/06/2021', 'Document 2021')
        row = Adapter.parse_projects(html)[0]
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fase'])
        self.assertEqual(row['id'], Adapter.parse_projects(html)[0]['id'])

    def test_fail_closed(self):
        for html in ['<h1>Login</h1>', fixture() + '<link rel="next" href="/page/2">',
                     fixture('<p><strong>Notícia</strong></p><ul><li><a href="/news">News</a></li></ul>'),
                     fixture().replace('<a href="/annex.pdf">Annex</a>', '<a href="javascript:x">Annex</a>'),
                     fixture('<ul><li><a href="/orphan.pdf">Unassigned</a></li></ul>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_snapshot_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            adapter = Adapter('sils')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, Path(directory)/'state')['rows'], 2)
                backfill.assert_called_once_with(path)
            Adapter._write(path, Adapter.parse_projects(fixture()))
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('sils')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.config['ine_code'], '17193')


if __name__ == '__main__':
    unittest.main()
