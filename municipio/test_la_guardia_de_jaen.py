"""Offline parser regression tests; no network or local evidence dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.la_guardia_de_jaen import (
    SOURCE, LaGuardiaDeJaenAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def instrument(area, approval="07/04/1989", publication="05/05/1989", file="memoria"):
    return f'''<div class="et-box et-bio"><ul><li>Ámbito: <strong>{area}</strong></li>
    <li>Fecha de aprobación: <strong>{approval}</strong> Fecha de publicación: {publication}</li></ul></div>
    <a href="/wp-content/uploads/{file}.pdf">Memoria {area}</a>
    <a href="/wp-content/uploads/{file}.pdf">Memoria duplicada</a>
    <a href="/unrelated-bop.pdf"> </a><a href="/pdf-icon.png"><img></a>
    <a href="/wp-content/uploads/{file}-plano.pdf">Plano {area}</a>'''


def page(content, category="Plan Parcial", extra=""):
    return f'''<article><div class="entry-content">{extra}<div class="et_pb_tabs">
    <ul class="et_pb_tabs_controls"><li>{category}</li></ul>
    <div class="et_pb_all_tabs"><div class="et_pb_tab"><div class="et_pb_tab_content">
    {content}</div></div></div></div></div></article>'''


class InventoryTests(unittest.TestCase):
    def test_grouping_dates_and_document_isolation(self):
        rows = parse_inventory(page(instrument("El Arrabal", file="arrabal") +
                                    instrument("El Fontanar", "21/13/2008", "–", "fontanar")))
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r["documentos"]) for r in rows], [2, 2])
        self.assertTrue(all("arrabal" in d["url"] for d in rows[0]["documentos"]))
        self.assertTrue(all("fontanar" in d["url"] for d in rows[1]["documentos"]))
        self.assertEqual(rows[0]["fecha_aprob"], "1989-04-07")
        self.assertEqual(rows[0]["fecha_publicacion"], "1989-05-05")
        self.assertNotIn("fecha_aprob", rows[1])
        self.assertNotIn("fecha_publicacion", rows[1])
        self.assertEqual(rows[1]["fecha_aprob_fuente"], "21/13/2008")
        self.assertTrue(rows[1]["avisos"])
        for row in rows:
            self.assertEqual(row["codigo_ine"], "23038")
            self.assertFalse(row["publication_ready"])
            self.assertNotIn("fecha_acuerdo", row)
            self.assertNotIn("lat", row)
            self.assertNotIn("fase", row)

    def test_source_inconsistency_preserved(self):
        row = parse_inventory(page(instrument("Ciudad Jardín", "30/12/1998", "03/04/1998")))[0]
        self.assertEqual(row["fecha_publicacion"], "1998-04-03")
        self.assertTrue(row["avisos"])

    def test_stable_identity_independent_of_order(self):
        a, b = instrument("A", file="a"), instrument("B", file="b")
        first = parse_inventory(page(a + b))
        second = parse_inventory(page(b + a))
        self.assertEqual(first[0]["id"], second[1]["id"])

    def test_reject_empty_unreviewed_or_paginated_inventory(self):
        cases = ["<html>maintenance</html>", page(""),
                 page(instrument("A"), category="Solicitud de licencia"),
                 page(instrument("A"), extra='<a rel="next" href="?page=2">2</a>'),
                 page(instrument("A"), extra='<a href="?page=2">Siguiente</a>'),
                 page(instrument("A") + instrument("A"))]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_missing_docs_fail_and_licence_form_does_not_become_project(self):
        html = page('<div class="et-bio">Ámbito: A Fecha de aprobación: – Fecha de publicación: –</div>'
                    '<a href="/licencia.doc">Solicitud de licencia</a>')
        with self.assertRaises(ValueError):
            parse_inventory(html)

    @patch("municipio.adapters.la_guardia_de_jaen.requests.get")
    def test_adapter_refresh_and_disabled_licences(self, get):
        response = Mock(url=SOURCE, text=page(instrument("A")))
        get.return_value = response
        with tempfile.TemporaryDirectory() as tmp:
            adapter = LaGuardiaDeJaenAyuntamientoAdapter("la-guardia-de-jaen")
            output = Path(tmp) / "proyectos.jsonl"
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / "state.json")["count"], 1)
            self.assertEqual(json.loads(output.read_text())["ambito"], "A")
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), "")

    def test_manifest(self):
        manifest = load_manifest("la-guardia-de-jaen")
        self.assertEqual(manifest.provincia, "Jaén")
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == "__main__":
    unittest.main()
