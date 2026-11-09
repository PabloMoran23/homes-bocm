import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.salas import SOURCE, SalasAyuntamientoAdapter, parse_projects
from municipio.manifest import load_manifest, load_yaml


def document(number, title):
    return (f'<a href="/c/document_library/get_file?uuid={number:08x}-0000-0000-0000-000000000000'
            f'&amp;groupId=1902209">{title}</a>')


def package(extra=""):
    return ('<div class="journal-content-article"><div class="detalle">'
            '<p>Plan General de Ordenación Urbana (PGOU)</p>'
            + document(1, "Memoria") + document(2, "Normativa") + extra + '</div></div>')


class SalasTests(unittest.TestCase):
    def test_groups_all_documents_and_excludes_navigation(self):
        html = document(900, "Solicitud de licencia") + package(
            ''.join(document(i, f"Plano {i}") for i in range(3, 85)) + document(1, "Memoria"))
        rows = parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["documentos"]), 84)
        self.assertTrue(all(d["source_url"] == SOURCE for d in rows[0]["documentos"]))
        self.assertFalse(any("Solicitud" in d["titulo"] for d in rows[0]["documentos"]))

    def test_no_inferred_dates_status_or_coordinates(self):
        row = parse_projects(package('<p>Copyright 2026</p>'))[0]
        for key in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "fase", "lat", "lon", "geometry"):
            self.assertIsNone(row[key])
        self.assertFalse(row["publication_ready"])
        self.assertEqual(row["codigo_ine"], "33059")

    def test_missing_or_ambiguous_source_rejected(self):
        for html in ("<h1>Salas</h1>", package().replace("Normativa", "Solicitud"), package() * 2):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_pagination_rejected(self):
        for control in ('<a rel="next" href="/pgo?x=2">Más</a>',
                        '<a href="/pgo?page=2">2</a>', '<div class="pagination"></div>',
                        '<a href="/pgo">Siguiente</a>'):
            with self.subTest(control=control), self.assertRaises(ValueError):
                parse_projects(package() + control)

    def test_document_provenance_rejected(self):
        with self.assertRaises(ValueError):
            parse_projects(package().replace('/c/document_library/', 'https://example.org/c/document_library/'))

    def test_live_path_refresh_and_disabled_licences(self):
        response = Mock(text=package(), url=SOURCE)
        adapter = SalasAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as temp, patch('municipio.adapters.salas.requests.get', return_value=response) as get:
            out, state = Path(temp) / 'proyectos.jsonl', Path(temp) / 'state.json'
            self.assertEqual(adapter.backfill_proyectos(out)["rows"], 1)
            first = out.read_text()
            adapter.update_proyectos(out, state)
            self.assertEqual(out.read_text(), first)
            self.assertEqual(json.loads(first)["url"], SOURCE)
            self.assertEqual(get.call_count, 2)
            adapter.update_licencias(out, state)
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('salas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Salas', 'Asturias', '33059'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
