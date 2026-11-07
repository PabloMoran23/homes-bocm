import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.huetor_vega import (
    ADAPTACION, NNSS, HuetorVegaAyuntamientoAdapter, _publication,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def table(header, links):
    heading = f"<thead><tr><th>{header}</th></tr></thead>" if header else ""
    body = "".join(f'<tr><td><a href="/wp-content/uploads/2024/04/{name}.pdf">{label}</a></td></tr>' for name, label in links)
    return f"<table>{heading}<tbody>{body}</tbody></table>"


def fixture(source):
    if source == NNSS:
        title = "Normas Subsidiarias – NNSS"
        tables = table("DOCUMENTACIÓN INICIAL 2002", [("normas", "Aprobación definitiva"), ("fichas", "FICHAS Aprobación definitiva")])
        tables += table("PLANOS INICIALES 2002", [("plano1", "01 Estructura general")])
        tables += table("MODIFICACIONES NNSS 2002", [
            ("bop1", "Modificaciones puntuales nº 1-3-7. BOP Nº292 de 22 diciembre 2003. Pág 48."),
            ("bop2", "Innovación a las NN.SS. en zona de Las Lomas. BOP Nº202 de 21 octubre 2010. Pág.34."),
        ])
        tables += table("PLANOS ACTUALES NN.SS. 2002", [("plano2", "Determinaciones 2a")])
    else:
        title = "PGOU Adaptación parcial NNSS"
        tables = table("DOCUMENTACIÓN", [("memoria", "MEMORIA A.P. HUETOR VEGA (ENERO 11)")])
        tables += table("PLANOS", [("adapt1", "1Na Clasificación")])
        tables += table(None, [("adapt2", "2Na Sistemas generales")])
    return f'<h2 class="entry-title">{title}</h2><section class="entry-content">{tables}</section>'


class HuetorVegaTests(unittest.TestCase):
    def test_group_documents_and_split_separate_numbered_instruments(self):
        rows = HuetorVegaAyuntamientoAdapter.parse_inventory(fixture(NNSS), NNSS)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(rows[0]["documentos"]), 4)
        self.assertEqual(len({r["id"] for r in rows}), 5)
        self.assertEqual({r["url_documento"] for r in rows[1:4]}, {rows[1]["url_documento"]})
        self.assertEqual(rows[1]["fecha_publicacion"], "2003-12-22")
        self.assertEqual(rows[-1]["fecha_publicacion"], "2010-10-21")
        for row in rows:
            self.assertIsNone(row["fecha_acuerdo"])
            self.assertIsNone(row["fecha_aprob"])
            self.assertIsNone(row["fecha"])
            self.assertIsNone(row["lat"])
            self.assertIsNone(row["fase"])
            self.assertEqual(row["codigo_ine"], "18101")

    def test_adaptation_groups_continuation_tables_no_upload_date(self):
        rows = HuetorVegaAyuntamientoAdapter.parse_inventory(fixture(ADAPTACION), ADAPTACION)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["documentos"]), 3)
        self.assertIsNone(rows[0]["fecha_publicacion"])
        self.assertIsNone(_publication("MEMORIA ENERO 11 /2024/04/"))
        self.assertEqual(_publication("BOP. Nº2 de 4 de enero de 2020"), "2020-01-04")

    def test_reject_pagination_incomplete_layout_and_non_documents(self):
        valid = fixture(NNSS)
        cases = [
            '<html>Acceso a sede. Solicitud de licencia</html>',
            valid + '<a rel="next" href="?page=2">2</a>',
            valid + '<a href="/page/2/">Siguiente</a>',
            valid + '<div class="pagination"><a href="?page=2">2</a></div>',
            valid.replace("DOCUMENTACIÓN INICIAL 2002", "OTROS"),
            valid.replace("MODIFICACIONES NNSS 2002", "Contratación"),
            valid.replace("/wp-content/uploads/2024/04/normas.pdf", "https://example.org/formulario.pdf"),
            valid.replace("de 22 diciembre 2003", "de 32 diciembre 2003"),
            valid.replace("de 22 diciembre 2003", "sin fecha"),
            valid.replace('</section>', '<a href="otro.pdf">Nuevo expediente</a></section>'),
        ]
        for html in cases:
            with self.subTest(html=html[:80]), self.assertRaises((ValueError, KeyError)):
                HuetorVegaAyuntamientoAdapter.parse_inventory(html, NNSS)

    def test_refresh_and_failure_preserves_previous_snapshot(self):
        adapter = HuetorVegaAyuntamientoAdapter("huetor-vega")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "projects.jsonl"
            with patch.object(adapter, "_fetch", side_effect=fixture) as fetch:
                report = adapter.update_proyectos(out, Path(directory) / "state.json")
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(report["rows"], 6)
            previous = out.read_text()
            self.assertEqual(len([json.loads(line) for line in previous.splitlines()]), 6)
            with patch.object(adapter, "_fetch", side_effect=[fixture(NNSS), "login"]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(previous, out.read_text())

    def test_manifest_resolves_and_licences_disabled(self):
        manifest = load_manifest("huetor-vega")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "18101")
        self.assertEqual(manifest.provincia, "Granada")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), HuetorVegaAyuntamientoAdapter)
        adapter = HuetorVegaAyuntamientoAdapter("huetor-vega")
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, "_fetch", side_effect=AssertionError("Licence fetch forbidden")):
            out = Path(directory) / "licencias.jsonl"
            self.assertEqual(adapter.backfill_licencias(out)["status"], "disabled")
            self.assertEqual(out.read_text(), "")


if __name__ == "__main__":
    unittest.main()
