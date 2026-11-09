import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.las_pedroneras import (
    BASE, INVENTORY, LasPedronerasAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


TITLE = 'PAU UA-Norte del Sector 1 "Hoya del Moro"'
URL = BASE + "/registros/pau/pau-ua-norte-del-sector-1-hoya-del-moro"


def inventory(municipality="Pedroñeras, Las", pager="", title=TITLE):
    return f'''<main><table><thead><tr><th class="views-field-municipios-clm">Municipio</th></tr></thead>
    <tbody><tr><td class="views-field-title"><a href="{URL}">{title}</a></td>
    <td class="views-field-municipios-clm">{municipality}</td>
    <td>01/01/2099</td></tr></tbody></table>{pager}</main>'''


def detail():
    return f'''<article class="node--type-programa-actuacion-urbanizadora"><h1>{TITLE}</h1>
    <div class="field--name-municipios-clm"><li>CUENCA</li><li>Pedroñeras, Las</li></div>
    <div class="field--name-field-fecha-aprobacion"><time datetime="2019-04-01T12:00:00Z">Fecha</time></div>
    <div class="field--name-field-datos-inscripcion"><div class="field__item">PAU inscrito el 5 de agosto de 2019 con el número 001/2019.</div></div>
    </article>'''


class ParserTests(unittest.TestCase):
    def test_exact_municipality_filter(self):
        self.assertEqual(parse_inventory(inventory())[0], {URL: TITLE})
        for place in ("Cuenca", "El Pedroñernoso", "Pedroñeras, Las y otro"):
            self.assertEqual(parse_inventory(inventory(place))[0], {})

    def test_layout_failure(self):
        with self.assertRaises(ValueError):
            parse_inventory("<main>Servicio no disponible</main>")

    def test_date_provenance_and_no_inference(self):
        row = parse_detail(detail(), URL, TITLE)
        self.assertEqual(row["fecha_aprob"], "2019-04-01")
        self.assertIn("5 de agosto de 2019", row["datos_inscripcion"])
        self.assertEqual(row["codigo_ine"], "16154")
        self.assertEqual(row["documentos"], [])
        for key in ("fecha", "fecha_publicacion", "fecha_acuerdo", "lat", "lon", "fase", "fecha_concesion"):
            self.assertNotIn(key, row)

    def test_missing_approval_is_not_invented(self):
        html = detail().replace('datetime="2019-04-01T12:00:00Z"', '')
        self.assertNotIn("fecha_aprob", parse_detail(html, URL, TITLE))

    def test_detail_identity(self):
        for html in (detail().replace("CUENCA", "TOLEDO"),
                     detail().replace("Pedroñeras, Las", "Cuenca"),
                     detail().replace(TITLE, "Otro PAU"), "<html></html>"):
            with self.assertRaises(ValueError):
                parse_detail(html, URL, TITLE)

    def test_documents_grouped_and_scoped(self):
        doc = '<a href="/sites/default/files/pau.pdf">Memoria</a>'
        html = detail().replace("</article>", doc + doc + "</article>")
        html += '<footer><a href="/sites/default/files/otro.pdf">Otro plan</a></footer>'
        row = parse_detail(html, URL, TITLE)
        self.assertEqual(len(row["documentos"]), 1)
        self.assertEqual(row["documentos"][0]["source_url"], URL)

    def test_pager_and_host_validation(self):
        pager = '<nav class="pager"><a href="?page=1">2</a><a rel="next" href="?page=1">Siguiente</a></nav>'
        self.assertEqual(parse_inventory(inventory(pager=pager))[1], [INVENTORY + "?page=1"])
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace(URL, "https://example.org/registros/pau/foo"))

    def test_complete_crawl_refresh_and_atomic_failure(self):
        adapter = LasPedronerasAyuntamientoAdapter("las-pedroneras")
        page2 = INVENTORY + "?page=1"
        sources = {
            INVENTORY: inventory("Cuenca", '<nav class="pager"><a href="?page=1">2</a></nav>'),
            page2: inventory(pager='<nav class="pager"><a href="/registros/pau-cu">Primera</a></nav>'),
            URL: detail(),
        }
        calls = []

        def fetch(session, url):
            calls.append(url)
            return sources[url]

        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, "_fetch", side_effect=fetch):
            output = Path(tmp) / "proyectos.jsonl"
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result["inventory_pages"], 2)
            self.assertEqual(calls, [INVENTORY, page2, URL])
            first = output.read_text()
            self.assertEqual(json.loads(first)["titulo"], TITLE)
            adapter.update_proyectos(output, Path(tmp) / "state.json")
            self.assertEqual(first, output.read_text())
            sources[URL] = "<html>error</html>"
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(first, output.read_text())

    def test_empty_target_inventory_fails(self):
        adapter = LasPedronerasAyuntamientoAdapter("las-pedroneras")
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, "_fetch", return_value=inventory("Cuenca")):
            output = Path(tmp) / "proyectos.jsonl"
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertFalse(output.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("las-pedroneras")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "16154")
        self.assertEqual(manifest.provincia, "Cuenca")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "licencias.jsonl"
            result = LasPedronerasAyuntamientoAdapter("las-pedroneras").backfill_licencias(output)
            self.assertTrue(result["disabled"])
            self.assertEqual(output.read_text(), "")


if __name__ == "__main__":
    unittest.main()
