import tempfile
import unittest
from pathlib import Path

from municipio.adapters.ulldecona import UlldeconaAyuntamientoAdapter, _dates
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture(extra=''):
    chapters = ''.join(
        f'<p><strong>– {name}</strong></p><p>Capítol municipal.</p>'
        f'<p><a href="https://ulldecona.cat/urbanisme/chapter{i}.pdf">Document {i}</a></p>'
        for i, name in enumerate(['TEXT NORMES SUBSIDIÀRIES', 'PLÀNOLS',
                                  'Paràmetres', 'Regulació sòl urbà', 'Regulació sòl no urbanitzable']))
    plan = '''<p><strong>– Pla Parcial – Sector residencial</strong></p>
      <p>Aprovat en sessió de 10 de juny de 2021 (DOGC núm. 8454 de data 9.7.2021).</p>
      <ul><li><a href="https://ulldecona.cat/urbanisme/sector.pdf">Normes</a></li>
      <li><a href="https://ulldecona.cat/urbanisme/sector-planols.pdf">Plànols</a></li></ul>'''
    return '<div class="journal-content-article"><div>' + chapters + plan + extra + '</div></div>'


class UlldeconaTests(unittest.TestCase):
    def test_grouping_and_dates(self):
        rows = UlldeconaAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 5)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[1]['fecha_acuerdo'], '2021-06-10')
        self.assertEqual(rows[1]['fecha_publicacion'], '2021-07-09')
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertTrue(all(r['lat'] is None and r['lon'] is None for r in rows))

    def test_stale_header_excluded_and_identity_stable(self):
        stale = '<div class="journal-content-article"><div class="accessdirecte_element">TEXT NORMES SUBSIDIÀRIES stale data</div></div>'
        rows = UlldeconaAyuntamientoAdapter.parse_projects(stale + fixture())
        changed = UlldeconaAyuntamientoAdapter.parse_projects(fixture().replace('sector.pdf', 'sector-v2.pdf'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in changed])

    def test_multiple_dates_preserved_not_collapsed(self):
        html = fixture().replace(
            '<ul><li>',
            '<p>Modificació aprovada en sessió de 10 de febrer de 2023 (DOGC núm. 8900 de data 21.4.2023).</p><ul><li>', 1)
        row = UlldeconaAyuntamientoAdapter.parse_projects(html)[1]
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['fechas_acuerdo'], ['2021-06-10', '2023-02-10'])
        self.assertEqual(row['fechas_publicacion_dogc'], ['2021-07-09', '2023-04-21'])
        self.assertEqual(_dates('Última actualització sense data'), [])
        self.assertEqual(_dates('9 d’abril de 2015'), ['2015-04-09'])

    def test_changed_or_empty_sources_fail(self):
        for html in ['<html>Login</html>', fixture() + fixture(),
                     fixture().replace('TEXT NORMES SUBSIDIÀRIES', 'Changed'),
                     fixture('<a rel="next" href="?page=2">Next</a>'),
                     fixture().replace('https://ulldecona.cat/', 'https://example.org/')]:
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                UlldeconaAyuntamientoAdapter.parse_projects(html)

    def test_unrelated_noise_map_excluded(self):
        extra = '<p>– Mapa de Capacitat Acústica del municipi d’Ulldecona.</p><p>Normativa acústica</p><ul><li><a href="https://ulldecona.cat/urbanisme/noise.pdf">Mapa</a></li></ul>'
        self.assertEqual(len(UlldeconaAyuntamientoAdapter.parse_projects(fixture(extra))), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('ulldecona')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '43156')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
