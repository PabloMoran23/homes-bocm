"""Offline parser contracts; real source captures are kept outside source files."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alfaro import (
    SOURCE, AlfaroAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory():
    return '''
    <a href="/agendaurbana/plan/modelo/accion-06/">3.06 – Acción (06) PERI Cerámicas</a>
    <a href="/agendaurbana/plan/modelo/accion-06/">3.06 – Acción (06) PERI Cerámicas</a>
    <a href="/agendaurbana/plan/modelo/accion-07/">3.07 – Acción (07) PERI Palacio Ramirez</a>
    <a href="/agendaurbana/plan/social/accion-14/">3.14 – Acción (14) Programa primer empleo</a>
    <a href="/agendaurbana/wp-content/uploads/2022/08/2.3-Sostenibilidad-economica-del-PERI-Ceramicas.pdf">Ver ficha</a>
    <a href="/agendaurbana/wp-content/uploads/2022/08/2.4-PERI-Palacio-Remirez.pdf">Ver ficha</a>
    <a href="https://example.org/agendaurbana/plan/accion-10/">3.10 – Acción (10) PERI Zona cuevas</a>
    <a href="/formulario.pdf">Solicitud de licencia</a>
    <a href="/noticias/">Licitación de obras</a>'''


def detail(title):
    return f'''<h1>{title}</h1><time>2022-08-25</time>
    <div class="elementor-widget-heading"><h2>Descripción de la acción</h2></div>
    <div class="elementor-widget-text-editor"><p>Se plantea transformar y reurbanizar el ámbito.</p></div>
    <h2>Financiación de la acción</h2><p>Otro contenido.</p>'''


class AlfaroParserTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        actions, total = parse_inventory(inventory())
        self.assertEqual(total, 3)
        self.assertEqual(len(actions), 2)
        self.assertEqual([a["number"] for a in actions], ["06", "07"])
        for action in actions:
            row = parse_detail(detail(action["titulo"]), action)
            self.assertEqual(len(row["documentos"]), 2)
            pdf = row["documentos"][1]["url"]
            self.assertIn("Ceramicas" if action["number"] == "06" else "Remirez", pdf)
            self.assertNotIn("Otro contenido", row["descripcion"])
            self.assertEqual(row["codigo_ine"], "26011")
            for field in ("fecha", "fecha_aprob", "fecha_acuerdo", "fecha_publicacion", "lat", "lon", "fase"):
                self.assertNotIn(field, row)

    def test_reject_empty_and_pagination(self):
        for html in ("<html>blocked</html>", inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory() + '<a class="page-numbers" href="/page/2/">2</a>'):
            with self.subTest(html=html[-80:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_missing_pdf_or_mismatched_detail_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace("2.4-PERI-Palacio-Remirez.pdf", "other.pdf"))
        action = parse_inventory(inventory())[0][0]
        for html in (detail("Different title"), '<h1>PERI Cerámicas</h1>'):
            with self.assertRaises(ValueError):
                parse_detail(html, action)

    def test_refresh_and_failed_fetch_preserve_output(self):
        adapter = AlfaroAyuntamientoAdapter("alfaro")
        actions, _ = parse_inventory(inventory())
        pages = {SOURCE: inventory(), **{a["url"]: detail(a["titulo"]) for a in actions}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "proyectos.jsonl"
            with patch.object(adapter, "_fetch", side_effect=pages.__getitem__):
                result = adapter.update_proyectos(output, Path(directory) / "state.json")
            self.assertEqual(result["count"], 2)
            before = output.read_text()
            self.assertEqual(len([json.loads(line) for line in before.splitlines()]), 2)
            with patch.object(adapter, "_fetch", side_effect=RuntimeError("offline")):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), before)
            with patch.object(adapter, "_fetch", side_effect=AssertionError("no licence source")):
                self.assertTrue(adapter.backfill_licencias(output)["disabled"])
            self.assertEqual(output.read_text(), "")

    def test_manifest(self):
        manifest = load_manifest("alfaro")
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw["codigo_ine"]),
                         ("Alfaro", "La Rioja", "26011"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == "__main__":
    unittest.main()
