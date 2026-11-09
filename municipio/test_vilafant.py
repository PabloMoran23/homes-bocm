import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vilafant import VilafantAyuntamientoAdapter, publication_date
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(body, modern=''):
    return ('<div id="content-core"><div id="parent-fieldname-text">'
            '<h2>2024 endavant</h2>' + modern +
            '<h2>Projectes i planejament en tràmit vigents 2020-23</h2>' + body +
            '<h2>Projectes i planejament en tràmit anteriors 2013-19</h2>'
            '<h4>Projecte antic</h4><a href="/old.pdf">Projecte</a></div></div>')


class VilafantTests(unittest.TestCase):
    def test_group_documents_and_do_not_invent_dates(self):
        rows = VilafantAyuntamientoAdapter.parse_projects(inventory('''
            <h4>Projecte de voreres</h4><p>Expedient X2023000893.
            Termini 28 de juny de 2023</p><ul>
            <li>Edicte aprovació inicial (<a href="/bop.pdf">BOP 17.05.2022</a>)</li>
            <li><a href="/projecte.pdf">Projecte</a></li></ul>'''))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['expediente'], 'X2023000893')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['fecha_publicacion'], '2022-05-17')
        self.assertIn('aprovació inicial', row['documentos'][0]['contexto'])
        for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])

    def test_current_work_and_exclusions(self):
        rows = VilafantAyuntamientoAdapter.parse_projects(inventory('''
            <h4>Suspensió de llicències</h4><a href="/s.pdf">Edicte</a>
            <h4>Sol·licitud de llicència</h4><a href="/form.pdf">Formulari</a>
            <h4>Notícia d'una festa</h4><a href="/news">Notícia</a>''', '''
            <ul><li>Maig 2025: <strong>Reurbanització del carrer Almogàvers</strong>
            <ul><li><a href="https://drive.google.com/file/example">Presentació</a></li>
            <li><a href="https://tauler.seu-e.cat/detall?idEdicte=example">Edicte i projecte</a></li></ul></li></ul>'''))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertIsNone(rows[0]['fecha_publicacion'])

    def test_repeated_instrument_is_one_record(self):
        block = '<h4>Projecte de voreres</h4><p>X2023000893</p><a href="/p.pdf">Projecte</a>'
        rows = VilafantAyuntamientoAdapter.parse_projects(inventory(block * 2))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)

    def test_fail_closed(self):
        good = '<h4>Projecte de voreres</h4><a href="/p.pdf">Projecte</a>'
        for html in ('<html>Login</html>', inventory(''), inventory('<h4>Projecte sense documents</h4>'),
                     inventory(good) + '<a rel="next" href="?page=2">2</a>',
                     inventory(good).replace('2024 endavant', '2025 endavant'),
                     inventory(good + '<p>X2023000893 X2023000585</p>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                VilafantAyuntamientoAdapter.parse_projects(html)

    def test_dates(self):
        for label, expected in [('BOP 15 d’Octubre 2021', '2021-10-15'),
                                ('DOGC 31 de gener de 2022', '2022-01-31'),
                                ('BOP 29.02.2019', None), ('PDF 26.01.2022', None),
                                ('Termini 3 de juliol de 2023', None)]:
            self.assertEqual(publication_date(label), expected)

    def test_adapter_manifest_and_update(self):
        manifest = load_manifest('vilafant')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, VilafantAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('state'))['rows'], 1)
            backfill.assert_called_once()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
