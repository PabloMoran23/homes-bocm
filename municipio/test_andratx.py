"""Offline parser and adapter-contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.andratx import AndratxAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def table(title, filename, date=""):
    return (f"<table><tbody><td>{title}</td><td><p>Memòria {filename}</p>"
            f"{date}<a href='/storage/uploads/{filename}.pdf'>Enlace</a></td></tbody></table>")


def panel(title, tables):
    return f"<div class='panel'><h2 class='panel-title'>{title}</h2>{tables}</div>"


def inventory():
    return "<h1>Planejament</h1>" + "".join([
        panel("7.1.1.A Refos (NNSS aprovades Consell)", table("Escrita", "normes")),
        panel("7.1.1.B NNSS aprovades Consell (maig 2023)", table("Plànols", "plànol 1")),
        panel("7.1.1.C Modificacions puntuals", table("Modificació puntual núm. 1.A/2024 NNSS", "mp1a")
              + table("Modificació puntual núm. 1.A/2024 documents anteriors", "mp1a-old")
              + table("Modificació puntual núm. 1.B/2024 NNSS", "mp1b")
              + table("Modificació puntual núm. 4 NNSS (BOIB núm. 62, de 13 de maig de 2023)", "mp4",
                      "<p>Fecha : 13-05-2023</p>")),
        panel("7.1.1.D NNSS 2007 (Derogades)", table("NNSS 2007", "old")),
        panel("7.1.1.E Estudio de detalle Sant Elm", table("Sant Elm", "ed")),
        panel("7.2. Gestió i execució del planejament",
              table("7.2.2. Expropiació ANS/1.A", "ans1")
              + table("7.2.8. Junta de Compensació UA/1 SE", "bases")),
        panel("7.2. Gestión y ejecución del planeamiento",
              table("7.2.8. Junta de Compensación UA/1 SE", "bases")),
    ])


class AndratxTests(unittest.TestCase):
    def test_grouping_and_bilingual_deduplication(self):
        rows = AndratxAyuntamientoAdapter.parse_projects(inventory())
        by_id = {r['id']: r for r in rows}
        self.assertEqual(len(rows), 7)
        self.assertEqual(len(by_id['andratx-proy-nnss-2023']['documentos']), 2)
        self.assertEqual(len(by_id['andratx-proy-mp-1a']['documentos']), 2)
        self.assertEqual(len(by_id['andratx-proy-gestion-8']['documentos']), 1)
        self.assertEqual(len(by_id['andratx-proy-gestion-8']['grupos_fuente']), 2)
        self.assertFalse(any(d['url'].endswith('/old.pdf') for r in rows for d in r['documentos']))
        self.assertIn('pl%C3%A0nol%201.pdf', by_id['andratx-proy-nnss-2023']['documentos'][1]['url'])

    def test_dates_and_geometry_are_not_invented(self):
        rows = AndratxAyuntamientoAdapter.parse_projects(inventory())
        row = next(r for r in rows if r['id'] == 'andratx-proy-mp-4')
        self.assertEqual(row['documentos'][0]['fecha_fuente_texto'], 'Fecha : 13-05-2023')
        self.assertEqual(row['documentos'][0]['titulo'], 'Memòria mp4')
        for r in rows:
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase']:
                self.assertIsNone(r[field])
            self.assertEqual(r['codigo_ine'], '07005')

    def test_rejects_pagination(self):
        for pager in ["<ul class='pagination'></ul>", "<a rel='next' href='?page=2'>2</a>",
                      "<a href='?page=2'>Següent</a>"]:
            with self.subTest(pager=pager), self.assertRaisesRegex(ValueError, 'agination|continuation'):
                AndratxAyuntamientoAdapter.parse_projects(inventory() + pager)

    def test_changed_or_missing_inventory_fails(self):
        for html in ['<h1>Login</h1>', inventory().replace("7.1.1.A", "7.1.1.F"),
                     inventory().replace('Derogades', 'vigents'),
                     inventory().replace('Modificació puntual núm. 1.B/2024 NNSS', 'Other item'),
                     inventory().replace("/storage/uploads/ans1.pdf", "https://example.org/ans1.pdf")]:
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                AndratxAyuntamientoAdapter.parse_projects(html)

    def test_missing_document_title_fails(self):
        with self.assertRaisesRegex(ValueError, 'missing its source title'):
            AndratxAyuntamientoAdapter.parse_projects(inventory().replace('<p>Memòria ans1</p>', ''))

    def test_manifest_and_live_path_with_mocked_transport(self):
        manifest = load_manifest('andratx')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07005')
        self.assertEqual(raw['provincia'], 'Illes Balears')
        for section, field in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertIs(raw[section][field], False)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch('municipio.adapters.andratx.requests.get') as get:
                response = get.return_value
                response.url = SOURCE
                response.text = inventory()
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
                self.assertEqual(result['rows'], 7)
                self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 7)
                response.text = '<h1>Error</h1>'
                before = output.read_bytes()
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
