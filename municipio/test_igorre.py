"""Offline parser/contract tests. Live validation is recorded separately in evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.igorre import (
    BASE, PAGE_PREFIX, SOURCE, IgorreAyuntamientoAdapter, parse_page, parse_stages,
)
from municipio.manifest import load_manifest, load_yaml


def links(*items):
    return "".join(f'<div class="link-item"><a href="{url}">{title}</a></div>' for title, url in items)


def document(url, title="Memoria"):
    return f'<td class="CSPFileName"><a href="{url}">{title}</a></td>'


def paged(url, page, total=2):
    return (f'<div id="plans"><div class="ms-WPBody"><span>Resultados {page} - {page} de {total}</span>'
            + document(BASE + f"/plan-{page}.pdf")
            + f'<ul class="pagination"><li><a href="{url}?page=1">1</a></li>'
              f'<li><a href="{url}?page=2">2</a></li></ul></div></div>')


class IgorreTests(unittest.TestCase):
    def setUp(self):
        self.initial = BASE + PAGE_PREFIX + "2024.aspx"
        self.provisional = BASE + PAGE_PREFIX + "2026.aspx"
        self.drawings = BASE + PAGE_PREFIX + "planos.aspx"
        self.index = links(("Aprobación inicial del PGOU", self.initial),
                           ("Aprobación provisional del PGOU", self.provisional))
        self.pages = {
            SOURCE: self.index,
            self.initial: document(BASE + "/shared.pdf") + links(("Planos", self.drawings)),
            self.provisional: document(BASE + "/shared.pdf"),
            self.drawings: paged(self.drawings, 1),
            self.drawings + "?page=2": paged(self.drawings, 2),
        }

    def run_adapter(self, path):
        pages = self.pages

        class Session:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url, **kwargs):
                class Response:
                    headers = {"Content-Type": "text/html; charset=utf-8"}

                    def raise_for_status(self):
                        pass

                response = Response()
                response.url = url
                response.text = pages[url]
                response.content = response.text.encode()
                return response

        with patch("municipio.adapters.igorre.requests.Session", Session), patch("municipio.adapters.igorre.time.sleep"):
            return IgorreAyuntamientoAdapter("igorre").backfill_proyectos(path)

    def test_grouping_provenance_pagination_and_no_inferred_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proyectos.jsonl"
            result = self.run_adapter(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["codigo_ine"], "48094")
            self.assertEqual(row["fase"], "aprobación provisional")
            self.assertEqual(len(row["documentos"]), 3)
            shared = next(d for d in row["documentos"] if d["url"].endswith("shared.pdf"))
            self.assertEqual(len(shared["procedencias"]), 2)
            self.assertIn(self.drawings + "?page=2", result["source_urls"])
            self.assertEqual(next(iter(result["pagination_validation"].values())), {"expected": 2, "extracted": 2})
            for field in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry"):
                self.assertIsNone(row[field])
            self.assertFalse(row["publication_ready"])

    def test_incomplete_pagination_preserves_previous_output(self):
        # A server repeating page 1 under page=2 must not silently pass.
        self.pages[self.drawings + "?page=2"] = self.pages[self.drawings]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proyectos.jsonl"
            path.write_text("previous snapshot")
            with self.assertRaisesRegex(ValueError, "Incomplete document inventory"):
                self.run_adapter(path)
            self.assertEqual(path.read_text(), "previous snapshot")

    def test_multiple_paged_lists_checked_independently(self):
        # Three SharePoint zones share one page query on the real 2026 page.
        # The smaller list is repeated on page 2; deduplication must be per list.
        smaller = paged(self.drawings, 1, total=1).replace('id="plans"', 'id="smaller"').replace('/plan-1.pdf', '/small.pdf')
        self.pages[self.drawings] += smaller
        self.pages[self.drawings + "?page=2"] += smaller
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_adapter(Path(tmp) / "out.jsonl")
            self.assertEqual(len(result["pagination_validation"]), 2)
            self.assertEqual(result["documents"], 4)

    def test_unsupported_pagination_rejected(self):
        for href in ("javascript:__doPostBack('x','Page$2')", "https://example.org/page=2"):
            with self.subTest(href=href), self.assertRaisesRegex(ValueError, "pagination"):
                parse_page(document(BASE + "/a.pdf") + f'<ul class="pagination"><a href="{href}">2</a></ul>', self.drawings)

    def test_forms_navigation_empty_and_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):
            parse_page('<nav><a href="/licencia.pdf">Solicitud licencia</a></nav>', SOURCE)
        with self.assertRaises(ValueError):
            parse_stages(links(("Noticias del PGOU", self.initial)))
        with self.assertRaises(ValueError):
            parse_stages(links(("Aprobación inicial del PGOU", self.initial)))
        with self.assertRaises(ValueError):
            parse_page(document("https://example.org/a.pdf"), SOURCE)

    def test_duplicate_links_and_fragments(self):
        pages, docs = parse_page(document(BASE + "/a.pdf#page=1") + document(BASE + "/a.pdf"), self.initial)
        self.assertEqual(pages, [])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["url"], BASE + "/a.pdf")

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("igorre")
        self.assertEqual(manifest.provincia, "Bizkaia")
        self.assertEqual(manifest.portal.adapter, "municipio.adapters.igorre:IgorreAyuntamientoAdapter")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "48094")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(raw["licencias"]["enabled"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "licencias.jsonl"
            result = IgorreAyuntamientoAdapter("igorre").update_licencias(path, Path(tmp) / "state")
            self.assertEqual(result, {"status": "disabled", "rows": 0})
            self.assertEqual(path.read_text(), "")


if __name__ == "__main__":
    unittest.main()
