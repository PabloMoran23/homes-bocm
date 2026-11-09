"""Parser and adapter contract tests; no live network needed for this suite."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.isla_mayor import (
    DOCUMENT_PATH, SOURCE_URL, IslaMayorAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def block(section, files, total=None):
    # Minimal markup and real file names from the official inventory.
    count = len(files) if total is None else total
    links = "".join(f'<tr><td><a href="{DOCUMENT_PATH}{path}">{title}</a></td></tr>'
                    for path, title in files)
    return (f'<div class="download-block"><div class="title">{section}</div>'
            f'<table><!-- listResultSize:{count} -->{links}</table></div>')


PREFIX = ('<h1 class="cat-title">Plan General de Ordenación Municipal</h1>'
          '<div class="detail-p">En este apartado se publicará la documentación disponible '
          'asociada al Plan General de Ordenación Municipal de Isla Mayor.</div>')
FIRST = ("fase-inicial/IM-Presentacion-INICIO-PGOM.pdf", "IM-Presentación INICIO PGOM")
RESOLUTION = ("RESOLUCION-FIRMADA-APROBACION-AVANCE.pdf", "RESOLUCIÓN FIRMADA APROBACIÓN AVANCE")
HTML = PREFIX + block("FASE INICIAL", [FIRST]) + block("FASE 3", [RESOLUTION])


class IslaMayorTests(unittest.TestCase):
    def test_one_instrument_retains_every_document_and_section(self):
        rows = parse_inventory(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["codigo_ine"], "41902")
        self.assertEqual(row["provincia"], "Sevilla")
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(row["documentos"][1]["secciones"], ["FASE 3"])
        self.assertTrue(row["documentos"][0]["url"].endswith(FIRST[0]))
        self.assertEqual(row["documentos"][0]["source_url"], SOURCE_URL)

    def test_no_dates_approval_or_coordinates_inferred_from_labels(self):
        row = parse_inventory(HTML)[0]
        for field in ("fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry"):
            self.assertIsNone(row[field])
        self.assertNotIn("fase", row)
        self.assertFalse(row["publication_ready"])

    def test_repeated_url_groups_section_provenance(self):
        row = parse_inventory(HTML + block("OTRA SECCIÓN", [FIRST]))[0]
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(row["documentos"][0]["secciones"], ["FASE INICIAL", "OTRA SECCIÓN"])

    def test_generic_page_navigation_and_empty_lists_are_not_records(self):
        for html in ("<h1>Servicio no disponible</h1>", PREFIX,
                     PREFIX + block("FASE 3", []), HTML.replace("de Isla Mayor.", "de otro municipio.")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_incomplete_collector_and_pagination_fail_explicitly(self):
        for html in (PREFIX + block("FASE INICIAL", [FIRST], total=2),
                     HTML + '<a href="?pagegalleryfiles-1=2">2</a>',
                     HTML + '<a rel="next" href="/next/">Siguiente</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_unparsed_or_unexpected_documents_fail(self):
        for html in (HTML + f'<a href="{DOCUMENT_PATH}nuevo.pdf">Nuevo</a>',
                     HTML.replace(DOCUMENT_PATH + FIRST[0], "https://example.org/licencia.pdf"),
                     HTML.replace(FIRST[0], "solicitud.doc")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    @patch("municipio.adapters.isla_mayor.requests.get")
    def test_live_contract_refreshes_and_preserves_output_on_failure(self, get):
        response = Mock(url=SOURCE_URL, text=HTML, content=HTML.encode())
        get.return_value = response
        adapter = IslaMayorAyuntamientoAdapter("isla-mayor")
        with TemporaryDirectory() as temp:
            output = Path(temp) / "proyectos.jsonl"
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result["count"], 1)
            adapter.update_proyectos(output, Path(temp) / "state.json")
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(json.loads(output.read_text())["titulo"],
                             "Plan General de Ordenación Municipal de Isla Mayor (PGOM)")
            previous = output.read_bytes()
            response.text = PREFIX
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            response.url = "https://example.org/"
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("isla-mayor")
        self.assertEqual(manifest.provincia, "Sevilla")
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter,
                         "municipio.adapters.isla_mayor:IslaMayorAyuntamientoAdapter")
        with TemporaryDirectory() as temp:
            output = Path(temp) / "licencias.jsonl"
            result = IslaMayorAyuntamientoAdapter("isla-mayor").backfill_licencias(output)
            self.assertTrue(result["disabled"])
            self.assertEqual(output.read_text(), "")


if __name__ == "__main__":
    unittest.main()
