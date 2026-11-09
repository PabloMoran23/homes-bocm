"""Offline parser and snapshot contract tests; no live network required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from municipio.adapters.arroyo_de_la_luz import ArroyoDeLaLuzAyuntamientoAdapter as Adapter
from municipio.adapters.arroyo_de_la_luz import DISCOVERY, INVENTORY, ROOT
from municipio.manifest import load_manifest, load_yaml
from municipio.entity_policy import classify


SELECTOR = '<select id="PtofiguraMunicipio"><option value="243" selected>Arroyo de la Luz</option></select>'


def link(ident="40407", label="Arroyo de la Luz - NNSS.R-001.M-022"):
    return (f'<a class="unenlaceafiguradeplaneamiento" href="#" '
            f'onclick="addTab(\'/SITEX/ptofiguras/viewsigcat/{ident}\',\'{label}\');">M-022 - V</a>')


def inventory(links=None):
    return SELECTOR + '<ul class="filetree">' + (links if links is not None else link()) + '</ul>'


DETAIL = '''<div id="infoplaneamiento40407"><table>
<tr><th>Figura urbanística</th><td>Modificación puntual n.º 20 de las Normas Subsidiarias</td></tr>
<tr><th>Ámbito territorial</th><td>Arroyo de la Luz</td><td class="campoconidsdemunicipiosparamapa">243</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Referencia</th><td>NNSS.R-001.M-022</td></tr>
<tr><th>Fecha AD</th><td>28/03/2023</td></tr>
<tr><th>Fecha de publicación AD</th><td>02/08/2023</td></tr>
<tr id="filatramite236235"><td>28/03/2023</td><td>Aprobación definitiva municipal</td></tr>
<tr id="filatramite236234"><td>02/08/2023</td><td><a href="https://doe.juntaex.es/pdfs/doe/2023/1480o/23081204.pdf">Publicación en DOE de la aprobación definitiva</a></td></tr>
</table></div>
<div id="archivosplaneamiento40407"><h3>Memoria justificativa</h3>
<a download="Memoria justificativa - c021mj.pdf" href="/SITEX/ptofiguras/downloaddocumento/13587">PDF</a>
<a download="Memoria justificativa - c021mj.pdf" href="/SITEX/ptofiguras/downloaddocumento/13587">PDF</a></div>'''
ITEM = {"sitex_id": "40407", "url": ROOT + "/SITEX/ptofiguras/viewsigcat/40407"}


class ArroyoParserTests(unittest.TestCase):
    def test_discovery_and_inventory_deduplicate_without_record_cap(self):
        self.assertEqual(Adapter.parse_municipality(SELECTOR), "243")
        links = ''.join(link(str(i)) for i in range(100)) + link("0")
        links += link("39826", "Plan Territorial Tajo-Salor")
        rows = Adapter.parse_inventory(inventory(links), "243")
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]["url"], ROOT + "/SITEX/ptofiguras/viewsigcat/0")

    def test_pagination_or_changed_inventory_fails(self):
        for html in (inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory() + '<a href="?page=2">Siguiente</a>',
                     inventory().replace("selected", ""), inventory(""),
                     inventory(link().replace("viewsigcat/40407", "other/40407"))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html, "243")

    def test_documents_grouped_and_dates_distinct(self):
        row = Adapter.parse_detail(DETAIL, ITEM, "243")
        self.assertEqual(row["fecha_aprob"], "2023-03-28")
        self.assertEqual(row["fecha_publicacion"], "2023-08-02")
        self.assertNotIn("fecha_acuerdo", row)
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(row["documentos"][1]["titulo"], "Memoria justificativa - c021mj.pdf")
        self.assertEqual(row["tramites"][0]["tramite"], "Aprobación definitiva municipal")
        self.assertEqual(row["expediente"], "NNSS.R-001.M-022")
        self.assertEqual(classify(row)["entity_type"], "expediente")
        self.assertIsNone(row["geometry"])
        self.assertIsNone(row["lat"])

    def test_missing_dates_and_attachments_are_not_invented(self):
        html = DETAIL.split('<div id="archivosplaneamiento')[0]
        html = html.replace("28/03/2023", "").replace("02/08/2023", "").replace("Vigente", "En trámite")
        # A catalogued instrument may have neither annexes nor dated procedures.
        html = html[:html.index('<tr id="filatramite')] + '</table></div>'
        row = Adapter.parse_detail(html, ITEM, "243")
        self.assertEqual(row["estado"], "En trámite")
        self.assertIsNone(row["fecha_aprob"])
        self.assertIsNone(row["fecha_publicacion"])
        self.assertEqual(row["documentos"], [])
        self.assertEqual(row["document_coverage"], "metadata_only")

    def test_bad_scope_date_or_missing_content_fails(self):
        for html in (DETAIL.replace(">243<", ">244<"),
                     DETAIL.replace("28/03/2023", "31/02/2023"),
                     '<p>Licencia de obras: formulario de solicitud</p>',
                     DETAIL.split('<div id="archivosplaneamiento')[0]
                     + '<a id="enlacearchivosplaneamiento40407">Consultar documentos</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_detail(html, ITEM, "243")

    def test_snapshot_update_and_failure_preserves_previous_output(self):
        class FixtureAdapter(Adapter):
            fail = False

            def _fetch(self, session, url, *, data=None):
                if url == DISCOVERY:
                    return SELECTOR
                if url == INVENTORY:
                    assert data == {"municipioseleccionado": "243"}
                    return inventory()
                return '<p>Unavailable</p>' if self.fail else DETAIL

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "proyectos.jsonl"
            adapter = FixtureAdapter("arroyo-de-la-luz")
            self.assertEqual(adapter.backfill_proyectos(path)["rows"], 1)
            original = path.read_text()
            adapter.update_proyectos(path, Path(tmp) / "state.json")
            self.assertEqual(path.read_text(), original)
            self.assertEqual(json.loads(original)["codigo_ine"], "10021")
            adapter.fail = True
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), original)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / "licencias.jsonl")["rows"], 0)

    def test_manifest_identity_and_disabled_operations(self):
        manifest = load_manifest("arroyo-de-la-luz")
        raw = load_yaml(manifest.path)
        self.assertEqual((raw["codigo_ine"], manifest.nombre, manifest.provincia),
                         ("10021", "Arroyo de la Luz", "Cáceres"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == "__main__":
    unittest.main()
