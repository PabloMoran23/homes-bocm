"""Offline parser and snapshot tests; run with python -m unittest municipio.test_niebla."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.niebla import (
    GALLERY_ROOT, SOURCE, NieblaAyuntamientoAdapter, group_instrument,
    page_url, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def section(gallery="PGOU_FIRMADO", filename="PGOU-05-Normas-Urbanisticas-marzo-2023_unlocked.pdf"):
    return (f'<div class="wrapper"><header><h2 class="title">APROBACION INICIAL PGOU FIRMADO</h2>'
            '<time datetime="2023-08-15T12:24:34.211+0200">15 agosto 2023</time></header>'
            f'<a href="{GALLERY_ROOT}{gallery}/{filename}">Normas urbanísticas</a></div>')


def pagination(current, last):
    return (
        '<ul class="pagination">'
        f'<li class="active"><a href="/es/descargas/?pagedownloadgallery={current}#downloadgallery">{current}</a></li>'
        f'<li><a href="/es/descargas/?pagedownloadgallery={last}#downloadgallery">&gt;&gt;</a></li></ul>'
    )


class FakeResponse:
    def __init__(self, url, html):
        self.url, self.text = url, html
        self.content = html.encode()

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, pages):
        self.pages, self.headers, self.calls = pages, {}, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        self.calls.append(url)
        return FakeResponse(url, self.pages[url])


class NieblaTests(unittest.TestCase):
    def test_groups_versions_and_excludes_forms_news_other_municipalities(self):
        html = section() + section("PGOU_APROBACION_PROVISIONAL_2024", "DOC05_normas_PGOU202403_d.pdf")
        html += ('<h2 class="title">FORMULARIOS LICENCIAS DE OBRA</h2>'
                 '<a href="/export/sites/niebla/es/.galleries/descargas-licencias-obras/form.pdf">Licencia</a>'
                 '<a href="/es/noticias/licitacion/">Contratación de obras</a>')
        docs, pages = parse_inventory(html, SOURCE)
        row = group_instrument(docs + docs, [SOURCE])
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(row["codigo_ine"], "21053")
        self.assertEqual({d["version"] for d in row["documentos"]},
                         {"aprobacion_inicial_2023", "aprobacion_provisional_2024"})
        self.assertEqual(pages, {1})
        for field in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "fase"):
            self.assertNotIn(field, row)
        self.assertFalse(row["publication_ready"])

    def test_documents_in_inactive_tabs_retained(self):
        docs, _ = parse_inventory('<div class="tab-pane fade">' + section() + '</div>', SOURCE)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["inventory_urls"], [SOURCE])

    def test_pagination_includes_intermediate_pages(self):
        _, pages = parse_inventory(section() + pagination(1, 5), SOURCE)
        self.assertEqual(pages, {1, 2, 3, 4, 5})

    def test_unreviewed_pagination_and_family_fail(self):
        for html in (
            section() + '<ul class="pagination"><a href="?page=2">2</a></ul>',
            section() + pagination(1, 101),
            section("PGOU_UNKNOWN"),
            section() + '<a rel="next" href="https://example.org/next">Next</a>',
        ):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_ignored_page_parameter_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(section() + pagination(1, 5), page_url(2))

    def test_empty_form_only_and_wrong_host_fail(self):
        for html in ("", '<h2 class="title">FORMULARIOS LICENCIAS DE OBRA</h2>',
                     section().replace(GALLERY_ROOT, "https://example.org" + GALLERY_ROOT)):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)
        with self.assertRaises(ValueError):
            group_instrument([], [SOURCE])

    def test_crawl_all_pages_and_atomic_failure(self):
        pages = {page_url(n): section(filename=f"normas-{n}.pdf") + pagination(n, 5) for n in range(1, 6)}
        session = FakeSession(pages)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "proyectos.jsonl"
            adapter = NieblaAyuntamientoAdapter("niebla")
            with patch("municipio.adapters.niebla.requests.Session", return_value=session):
                result = adapter.backfill_proyectos(out)
            self.assertEqual(len(session.calls), 5)
            self.assertEqual(result["documents"], 5)
            row = json.loads(out.read_text())
            self.assertEqual(len(row["source_urls"]), 5)
            self.assertTrue(row["tls_verified"])
            before = out.read_bytes()
            pages[page_url(3)] = "invalid source"
            with patch("municipio.adapters.niebla.requests.Session", return_value=FakeSession(pages)):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(out, Path(tmp) / "state.json")
            self.assertEqual(out.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("niebla")
        raw = load_yaml(manifest.path)
        self.assertEqual((raw["codigo_ine"], raw["provincia"]), ("21053", "Huelva"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "licencias.jsonl"
            result = NieblaAyuntamientoAdapter("niebla").backfill_licencias(out)
            self.assertTrue(result["disabled"])
            self.assertEqual(out.read_text(), "")


if __name__ == "__main__":
    unittest.main()
