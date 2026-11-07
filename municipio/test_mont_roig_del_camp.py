"""Offline parser and snapshot integrity tests; no network required."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.mont_roig_del_camp import (
    MontRoigDelCampAyuntamientoAdapter, SOURCES, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

PROJECTS, PLANNING = list(SOURCES)


def page(content, source=PLANNING):
    return f'<h1>{SOURCES[source]}</h1><div class="wpb_text_column"><div class="wpb_wrapper">{content}</div></div>'


def project(number="13218/2026", title="Rotonda", phase="Aprovació inicial:"):
    return f'''<h4>{number} Projecte d’urbanització {title}</h4>
    <p>{phase}</p><ul><li><a href="/wp-content/uploads/edict-{title}.pdf">Edicte</a><a href="/wp-content/uploads/edict-{title}.pdf"> annex</a></li></ul>
    <p>Documentació:</p><ul><li><a href="/wp-content/uploads/project-{title}.pdf">Projecte</a></li></ul>'''


class InventoryTests(unittest.TestCase):
    def test_group_documents_and_distinguish_projects(self):
        rows = parse_inventory(page(project() + project("2639/2026", "Vial", "Exposició pública:")), PLANNING)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]["documentos"]), 2)
        self.assertEqual(rows[0]["documentos"][0]["titulo"], "Edicte annex")
        self.assertEqual(rows[0]["expediente"], "13218/2026")
        self.assertEqual(rows[0]["fase"], "aprobación inicial")
        self.assertEqual(rows[1]["fase"], "exposición pública")
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def test_no_inferred_dates_or_coordinates(self):
        html = '<meta property="article:modified_time" content="2026-11-07">' + page(project())
        row = parse_inventory(html, PLANNING)[0]
        for field in ("fecha", "fecha_publicacion", "fecha_aprob", "fecha_acuerdo", "lat", "lon", "geometry"):
            self.assertIsNone(row[field])
        self.assertFalse(row["publication_ready"])
        self.assertEqual(row["codigo_ine"], "43092")

    def test_unnumbered_municipal_project(self):
        html = page('<p>Projectes municipals en exposició pública</p>' + project("", "entorn del cotxe restaurant", "Documents:"), PROJECTS)
        row = parse_inventory(html, PROJECTS)[0]
        self.assertIsNone(row["expediente"])
        self.assertEqual(row["fase"], "exposición pública")
        self.assertEqual(row["id"], parse_inventory(html.replace("project-entorn", "replacement-entorn"), PROJECTS)[0]["id"])

    def test_reject_missing_or_non_project_content(self):
        for html in ("<h1>Login</h1>", page('<a href="form.pdf">Llicència d’obres</a>'),
                     page('<h4>Sol·licitud de llicència</h4>'), page('<h4>Projecte d’urbanització X</h4>'),
                     page(project(phase="Documentació:"))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, PLANNING)

    def test_reject_pagination_and_external_documents(self):
        for change in ('<a rel="next" href="?page=2">2</a>', '<div class="pagination">2</div>'):
            with self.assertRaisesRegex(ValueError, "pagination"):
                parse_inventory(page(project()) + change, PLANNING)
        with self.assertRaisesRegex(ValueError, "document URL"):
            parse_inventory(page(project()).replace('/wp-content/uploads/', 'https://example.org/'), PLANNING)

    def test_snapshot_failure_preserves_previous_output(self):
        class Response:
            url = PROJECTS
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size):
                yield page('<p>exposició pública</p>' + project(), PROJECTS).encode()
        with TemporaryDirectory() as folder:
            out = Path(folder) / "proyectos.jsonl"
            out.write_text("previous\n")
            with patch('municipio.adapters.mont_roig_del_camp.requests.get', side_effect=[Response(), RuntimeError("network unavailable")]):
                with self.assertRaises(RuntimeError):
                    MontRoigDelCampAyuntamientoAdapter("mont-roig-del-camp").backfill_proyectos(out)
            self.assertEqual(out.read_text(), "previous\n")

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("mont-roig-del-camp")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "43092")
        self.assertEqual(manifest.provincia, "Tarragona")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as folder:
            out = Path(folder) / "licencias.jsonl"
            result = MontRoigDelCampAyuntamientoAdapter(manifest.slug).backfill_licencias(out)
            self.assertEqual(result["rows"], 0)
            self.assertEqual(out.read_text(), "")


if __name__ == "__main__":
    unittest.main()
