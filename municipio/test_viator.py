import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.viator import (
    SOURCE, ViatorAyuntamientoAdapter, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(title="NN.SS. de Viator", path="nnss", navigation=""):
    return (f'<article class="category-normativa"><h2><a href="/{path}/">'
            f'{title}</a></h2></article>{navigation}')


def detail(title="NN.SS. de Viator", document="capitulo1.pdf"):
    return (f'<h1 class="single-title">{title}</h1><article><div class="single-entry-summary">'
            '<div class="date-meta"><span class="posted-date-month">Abr</span>'
            '<span class="posted-date-day">15</span><span class="posted-date-year">2011</span></div>'
            f'<a href="/docs/{document}">Capítulo</a><a href="/docs/{document}">Duplicado</a>'
            '<a href="/docs/plano.pdf">Plano</a></div></article>'
            '<aside><a href="/unrelated.pdf">Unrelated</a></aside>')


class ViatorTests(unittest.TestCase):
    def test_groups_documents_and_preserves_date_meaning(self):
        entry = parse_inventory(inventory())[0][0]
        row = parse_instrument(detail(), entry)
        self.assertEqual(row["codigo_ine"], "04101")
        self.assertEqual(row["fecha_publicacion"], "2011-04-15")
        self.assertEqual(len(row["documentos"]), 2)
        self.assertTrue(all(d["source_url"] == entry["url"] for d in row["documentos"]))
        for key in ("fecha", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry", "fase"):
            self.assertNotIn(key, row)
        self.assertEqual(row["id"], parse_instrument(detail(document="changed.pdf"), entry)["id"])

    def test_excludes_forms_procurement_and_news(self):
        for title in ("Solicitud de licencia de obras", "Licitación de obra", "Ordenanzas Municipales",
                      "Fiestas locales", "Proyecto educativo municipal"):
            self.assertEqual(parse_inventory(inventory(title))[0], [])

    def test_fails_closed_on_changed_or_empty_sources(self):
        entry = parse_inventory(inventory())[0][0]
        for html in ("", "<h1>Error</h1>"):
            with self.assertRaises(ValueError):
                parse_inventory(html)
        for html in (detail().replace('.pdf', '.txt'), detail(title="Other"),
                     detail() + '<div class="page-links"><a href="/2/">2</a></div>'):
            with self.assertRaises(ValueError):
                parse_instrument(html, entry)
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('/nnss/', 'https://unofficial.example/plan/'))

    def test_inventory_pagination_and_refresh(self):
        second = SOURCE + "page/2/"
        pages = {
            SOURCE: inventory(navigation=f'<a class="next page-numbers" href="{second}">Siguiente</a>'),
            second: inventory("Adaptación parcial a la L.O.U.A.", "adaptacion",
                              f'<a class="page-numbers" href="{SOURCE}">1</a>'),
            "https://ayuntamientoviator.es/nnss/": detail(),
            "https://ayuntamientoviator.es/adaptacion/": detail("Adaptación parcial a la L.O.U.A.", "memoria.pdf"),
        }

        class Response:
            def __init__(self, url):
                self.url, self.text = url, pages[url]
            def raise_for_status(self):
                pass

        with TemporaryDirectory() as directory, patch("municipio.adapters.viator.requests.get", side_effect=lambda url, **kw: Response(url)) as get:
            out = Path(directory) / "proyectos.jsonl"
            adapter = ViatorAyuntamientoAdapter("viator")
            report = adapter.update_proyectos(out, Path(directory) / "state.json")
            self.assertEqual(report["count"], 2)
            self.assertEqual(report["inventory_pages"], 2)
            self.assertEqual(get.call_count, 4)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertIn("memoria.pdf", rows[1]["documentos"][0]["url"])
            self.assertNotIn("memoria.pdf", str(rows[0]["documentos"]))
            # A detail failure must not overwrite the previous complete output.
            before = out.read_text()
            pages["https://ayuntamientoviator.es/adaptacion/"] = "Error"
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(before, out.read_text())

    def test_manifest_contract(self):
        manifest = load_manifest("viator")
        self.assertEqual(manifest.provincia, "Almería")
        self.assertFalse(manifest.licencias.enabled)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "04101")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])


if __name__ == "__main__":
    unittest.main()
