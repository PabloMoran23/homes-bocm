import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.yuncler import SOURCE, YunclerAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return '''<div class="elementor-accordion-item">
      <a class="elementor-accordion-title">URBANISMO</a>
      <div class="elementor-tab-content">
        <div>Desarrollando nuestro Plan General de Ordenación Municipal</div>
        <div><strong>Plan de ordenación</strong></div>
        <div><a href="/wp-content/uploads/normas.pdf">Normas urbanísticas</a></div>
        <div><a href="/wp-content/uploads/fichas.pdf">Fichas</a></div>
        <div><a href="/wp-content/uploads/general.pd">General</a></div>
        <div><a href="/wp-content/uploads/normas.pdf">Normas urbanísticas</a></div>
        <div><strong>Ordenanzas:</strong></div>
        <div><a href="/wp-content/uploads/tasa.pdf">Tasas</a></div>
      </div></div><a href="/wp-content/uploads/licencia.pdf">Solicitud de licencia</a>'''


class YunclerTests(unittest.TestCase):
    def test_grouping_scope_and_semantics(self):
        rows = YunclerAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["codigo_ine"], "45203")
        self.assertEqual([d["titulo"] for d in row["documentos"]],
                         ["Normas urbanísticas", "Fichas", "General"])
        self.assertTrue(row["documentos"][-1]["url"].endswith(".pd"))
        self.assertTrue(all(d["source_url"] == SOURCE for d in row["documentos"]))
        for field in ("fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry"):
            self.assertIsNone(row[field])
        self.assertNotIn("fase", row)
        self.assertFalse(row["publication_ready"])

    def test_reject_missing_ambiguous_or_changed_sources(self):
        for html in ("", fixture().replace("Fichas", "Formulario"),
                     fixture() + fixture(), fixture().replace("Plan de ordenación", "Servicios"),
                     fixture().replace("/wp-content/uploads/fichas.pdf", "https://other.test/f.pdf")):
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                YunclerAyuntamientoAdapter.parse_projects(html)

    def test_pagination_fails_explicitly(self):
        html = fixture().replace("<div><strong>Plan", '<a href="?page=2" rel="next">2</a><div><strong>Plan')
        with self.assertRaisesRegex(ValueError, "Paginated"):
            YunclerAyuntamientoAdapter.parse_projects(html)

    def test_snapshot_update_and_disabled_licences(self):
        adapter = YunclerAyuntamientoAdapter("yuncler")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "proyectos.jsonl"
            with patch.object(adapter, "backfill_proyectos", return_value={"rows": 1}) as backfill:
                self.assertEqual(adapter.update_proyectos(output, Path(directory) / "state"), {"rows": 1})
                backfill.assert_called_once_with(output)
            adapter._write(output, adapter.parse_projects(fixture()))
            self.assertEqual(json.loads(output.read_text())["id"], "yuncler-pom")
            self.assertEqual(adapter.backfill_licencias(output)["status"], "disabled")
            self.assertEqual(output.read_text(), "")

    def test_manifest(self):
        manifest = load_manifest("yuncler")
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw["codigo_ine"]),
                         ("Yuncler", "Toledo", "45203"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == "__main__":
    unittest.main()
