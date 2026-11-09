import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_pobla_de_mafumet import (
    BOPT, PDF, SOURCE, LaPoblaDeMafumetAyuntamientoAdapter, parse_bopt, parse_inventory,
)
from municipio.manifest import load_manifest


def inventory(body):
    return '<title>Documents subjectes a exposició pública. | Ajuntament</title><div class="page-content">' + body + '</div>'


PLAN = '<h2>Aprovació inicial de la modificació puntual núm.6 del POUM</h2><p><a href="https://drive.google.com/file/d/example/view">Modificació puntual del POUM Àmbit del PAU‐I</a></p>'
NOTICE = '''<h1>Modificació puntual núm. 6 del Pla d'Ordenació Urbanística Municipal, POUM. Aprovació inicial.</h1>
<p>AJUNTAMENT POBLA DE MAFUMET, LA</p><p>Data de publicació: 22/10/2025</p>
<p>Número de Registre: 2025-09478</p><a href="/bopt/web/anunci/descarrega-pdf/351869">PDF</a>'''


class PlanningTests(unittest.TestCase):
    def test_only_actual_planning_and_no_invented_dates(self):
        unrelated = '<h2>Autorització Ambiental DOW CHEMICAL</h2><p><a href="/environment.pdf">Resolució</a></p><h2>Sol·licitud de llicència</h2><p><a href="/form.pdf">Formulari</a></p>'
        rows = parse_inventory(inventory(unrelated + PLAN))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['codigo_ine'], '43109')
        self.assertEqual(len(rows[0]['documentos']), 1)
        for key in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry']:
            self.assertIsNone(rows[0][key])

    def test_group_documents_and_stable_identity(self):
        a = parse_inventory(inventory(PLAN))[0]
        second = PLAN.replace('example/view', 'second/view')
        b = parse_inventory(inventory(PLAN + second + PLAN))[0]
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(len(b['documentos']), 2)
        self.assertEqual(b['documentos'][0]['procedencia'], SOURCE)

    def test_fail_closed(self):
        for html in ['<title>Login</title>', inventory('<h2>Informació</h2>'),
                     inventory('<h2>Aprovació inicial de la modificació puntual núm.6 del POUM</h2>'),
                     inventory(PLAN + '<a rel="next" href="/page/2">2</a>'),
                     inventory(PLAN + '<a href="?paged=2">2</a>'),
                     inventory(PLAN + PLAN.replace('inicial', 'definitiva'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_notice_identity_and_publication_semantics(self):
        self.assertEqual(parse_bopt(NOTICE + '<p>Signatura: 14/10/2025</p>'), '2025-10-22')
        for html in [NOTICE.replace('núm. 6', 'núm. 5'), NOTICE.replace('POBLA DE MAFUMET', 'ALTRE MUNICIPI'),
                     NOTICE.replace('22/10/2025', '31/02/2025'), NOTICE.replace('Data de publicació:', 'Actualització:'),
                     NOTICE.replace(PDF.split('.cat')[1], '/other.pdf')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_bopt(html)

    def test_live_path_groups_supplement_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = LaPoblaDeMafumetAyuntamientoAdapter('la-pobla-de-mafumet')
            output = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(PLAN).encode(), NOTICE.encode(), b'%PDF-1.7']):
                report = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(report['rows'], 1)
            row = json.loads(output.read_text())
            self.assertEqual(row['fecha_publicacion'], '2025-10-22')
            self.assertIsNone(row['fecha_aprob'])
            self.assertEqual(len(row['documentos']), 2)
            self.assertEqual(report['source_urls'], [SOURCE, BOPT, PDF])
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('la-pobla-de-mafumet')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
