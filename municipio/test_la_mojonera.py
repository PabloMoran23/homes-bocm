"""Offline parser and traversal regressions; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_mojonera import (
    INVENTORY, ROOT, LaMojoneraAyuntamientoAdapter,
    group_instruments, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

HEADERS = """<thead><tr><th>Órgano Tramitador</th><th>Actuación</th><th>Provincia</th>
<th>Otras Provincias</th><th>Municipio</th><th>Otros Municipios</th>
<th>Tipo de Resolución</th><th>Fecha de Resolución</th><th>Número de Expediente</th>
<th>Resoluciones y Otros Documentos (*)</th></tr></thead>"""


def inventory(page=1, total=1, number=7708, ref="EAE/AL/011/17"):
    return f"""<table>{HEADERS}<tr><td>Delegación Almería</td>
<td>Innovación nº 7 del PGOU de La Mojonera</td><td>ALMERÍA</td><td></td>
<td>MOJONERA (LA)</td><td></td><td>Admisión/ Inadmisión Trámite</td>
<td>25/07/2017</td><td>{ref}</td><td><a href="/medioambiente/daepu/resolucions/{number};jsessionid=TEMP">Ver</a></td>
</tr><tr class="footer"><td colspan="10">Página {page} de {total}</td></tr></table>"""


def detail(ref="EAE/AL/011/17", doc="document-one"):
    return f"""<div><label>Provincia:</label><div class="box">ALMERÍA</div></div>
<div><label>Municipio:</label><div class="box">MOJONERA (LA)</div></div>
<div><label>Número de Expediente:</label><div class="box">{ref}</div></div>
<table><thead><tr><th>Tipo</th><th>Fecha de Resolución</th><th>Enlace al documento</th></tr></thead>
<tr><td>Informe Ambiental Estratégico (IAE)</td><td>31/07/2018</td>
<td><a href="downloadFile/{doc}">Documento</a></td></tr>
<tr><td>Publicación en BOJA (PB)</td><td>28/09/2018</td>
<td><a href="downloadFile/publication">Documento</a></td></tr>
<tr class="footer"><td colspan="4"></td></tr></table>"""


class LaMojoneraTests(unittest.TestCase):
    def test_inventory_identity_and_session_free_links(self):
        rows, current, total = parse_inventory(inventory(), INVENTORY)
        self.assertEqual((current, total), (1, 1))
        self.assertEqual(rows[0]["url"], ROOT + "/7708")
        self.assertEqual(rows[0]["fecha_resolucion_ambiental"], "2017-07-25")
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace("MOJONERA (LA)", "ROQUETAS DE MAR"), INVENTORY)
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace("ALMERÍA", "MÁLAGA"), INVENTORY)

    def test_dates_are_environmental_or_publication_never_plan_approval(self):
        docs = parse_detail(detail(), ROOT + "/7708", "EAE/AL/011/17")
        self.assertEqual(docs[0]["fecha_resolucion_ambiental"], "2018-07-31")
        self.assertNotIn("fecha_publicacion", docs[0])
        self.assertEqual(docs[1]["fecha_publicacion"], "2018-09-28")
        self.assertNotIn("fecha_resolucion_ambiental", docs[1])
        self.assertEqual(docs[0]["url"], ROOT + "/downloadFile/document-one")
        self.assertNotIn("fecha_aprob", json.dumps(docs))

    def test_grouping_retains_distinct_documents_and_provenance(self):
        a = parse_inventory(inventory(), INVENTORY)[0][0]
        b = parse_inventory(inventory(number=44381, ref="(EAE/AL/011/17)"), INVENTORY)[0][0]
        c = parse_inventory(inventory(number=52841, ref="EAE/AL/027/25"), INVENTORY)[0][0]
        records = group_instruments([
            (a, parse_detail(detail(), a["url"], a["expediente"])),
            (b, parse_detail(detail(doc="document-two"), b["url"], b["expediente"])),
            (c, parse_detail(detail("EAE/AL/027/25", "sector22"), c["url"], c["expediente"])),
        ])
        self.assertEqual(len(records), 2)
        self.assertEqual(len(records[0]["fichas"]), 2)
        self.assertEqual(len(records[0]["documentos"]), 4)
        self.assertEqual(records[0]["codigo_ine"], "04903")
        self.assertNotIn("sector22", json.dumps(records[0]))
        self.assertNotIn("lat", records[0])
        self.assertFalse(records[0]["publication_ready"])
        self.assertEqual(records[0]["id"], group_instruments([(a, [])])[0]["id"])

    def test_missing_content_and_pagination_fail_closed(self):
        for html in ["Please enable JavaScript", "<table></table>",
                     inventory().replace("Página 1 de 1", ""),
                     inventory().replace("25/07/2017", "31/02/2017")]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html, INVENTORY)

    def test_document_mismatch_missing_and_untrusted_links(self):
        for html in [detail("EAE/AL/099/99"), detail().replace("downloadFile/document-one", "https://example.org/file.pdf"),
                     detail().replace("<a href=\"downloadFile/document-one\">Documento</a>", "Sin enlace")]:
            with self.assertRaises(ValueError):
                parse_detail(html, ROOT + "/7708", "EAE/AL/011/17")

    def run_mock(self, output, second_page):
        responses = [inventory(total=2), detail(), second_page, detail("EAE/AL/027/25", "sector22")]
        class Response:
            def __init__(self, html, url):
                self.content, self.url = html.encode(), url
            def raise_for_status(self):
                pass
        with patch("municipio.adapters.la_mojonera.requests.Session") as cls:
            session = cls.return_value.__enter__.return_value
            session.get.side_effect = lambda url, **kw: Response(responses.pop(0), url)
            result = LaMojoneraAyuntamientoAdapter("la-mojonera").backfill_proyectos(output)
            return result, session.get.call_args_list

    def test_full_pagination_and_no_partial_output_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "proyectos.jsonl"
            result, calls = self.run_mock(output, inventory(2, 2, 52841, "EAE/AL/027/25"))
            self.assertEqual(result["count"], 2)
            self.assertEqual(len(output.read_text().splitlines()), 2)
            self.assertIn("page=2", calls[2].args[0])
            output.write_text("previous-success")
            with self.assertRaises(ValueError):
                self.run_mock(output, inventory(1, 2))
            self.assertEqual(output.read_text(), "previous-success")

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("la-mojonera")
        raw = load_yaml(manifest.path)
        self.assertEqual((raw["codigo_ine"], manifest.provincia), ("04903", "Almería"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "licencias.jsonl"
            result = LaMojoneraAyuntamientoAdapter("la-mojonera").backfill_licencias(path)
            self.assertTrue(result["disabled"])
            self.assertEqual(path.read_text(), "")


if __name__ == "__main__":
    unittest.main()
