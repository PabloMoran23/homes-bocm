import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import requests

from municipio.adapters.santa_cruz_del_retamar import (
    SOURCE, SantaCruzDelRetamarAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


HTML = """<section><h2>Urbanismo</h2>
<p>PLAN DE ORDENACION MUNICIPAL</p>
<p><a href="pomdocm.pdf">Edicto Aprobación P.O.M. Diario Oficial</a></p>
<p><a href="pombop.pdf">Edicto Aprobación P.O.M. Boletín Provincial</a></p>
<p><a href="ordenacion.rar">Planos Plan de ordenación municipal</a></p>
<p><a href="NORMASpom.pdf#zoom=100">Normas.</a></p>
<p><a href="MEMORIA.pdf">Memoria.</a></p>
<p>NOTAS:</p>
<p>MODELOS DE SOLICITUD URBANÍSTICA:</p>
<a href="licencia.pdf">Licencia de Parcelación.</a>
<a href="basespau.pdf">BASES REGULADORAS P.A.U. DOT1</a>
</section>"""


class InventoryTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_metadata(self):
        rows = parse_inventory(HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["codigo_ine"], "45157")
        self.assertEqual(len(row["documentos"]), 5)
        self.assertTrue(all(d["inventory_url"] == SOURCE for d in row["documentos"]))
        self.assertTrue(all("#" not in d["url"] for d in row["documentos"]))
        self.assertFalse(any("licencia" in d["url"] or "basespau" in d["url"] for d in row["documentos"]))
        for key in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "fase"):
            self.assertNotIn(key, row)

    def test_deduplicates_documents(self):
        extra = '<a href="MEMORIA.pdf#zoom=200">Memoria duplicada</a>'
        self.assertEqual(len(parse_inventory(HTML.replace('<p>NOTAS:', extra + '<p>NOTAS:'))[0]["documentos"]), 5)

    def test_refuses_empty_incomplete_or_changed_structure(self):
        for html in ("<html>Acceso denegado</html>", HTML.replace("NOTAS:", ""),
                     HTML.replace("PLAN DE ORDENACION MUNICIPAL", "Otro inventario"),
                     HTML.replace("Normas.", "Documento sin identificar")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_refuses_pagination(self):
        for link in ('<a href="?page=2">2</a>', '<a href="otra.html" rel="next">Más</a>',
                     '<a href="otra.html">Siguiente</a>'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                parse_inventory(HTML.replace("</section>", link + "</section>"))

    def test_refuses_foreign_documents_and_inventory(self):
        with self.assertRaises(ValueError):
            parse_inventory(HTML.replace('href="MEMORIA.pdf"', 'href="https://example.org/a.pdf"'))
        with self.assertRaises(ValueError):
            parse_inventory(HTML, "https://example.org/Urbanismo/Urbanismo.html")

    @staticmethod
    def session(bad_document=False, http_error=False):
        session = MagicMock()
        page = MagicMock(content=HTML.encode(), url=SOURCE)
        def get(url, **kwargs):
            if url == SOURCE:
                return page
            result = MagicMock(url=url, status_code=200, headers={"Content-Type": "application/pdf"})
            if http_error:
                result.raise_for_status.side_effect = requests.HTTPError("404")
            prefix = b"Rar!\x1a\x07\x00" if url.endswith(".rar") else b"%PDF-1.7"
            result.iter_content.return_value = iter([b"<html>error" if bad_document else prefix])
            result.__enter__.return_value = result
            return result
        session.get.side_effect = get
        session.__enter__.return_value = session
        return session

    def test_snapshot_update_and_disabled_licences(self):
        with TemporaryDirectory() as directory, patch(
            "municipio.adapters.santa_cruz_del_retamar.requests.Session", return_value=self.session()
        ):
            out = Path(directory) / "proyectos.jsonl"
            adapter = SantaCruzDelRetamarAyuntamientoAdapter("santa-cruz-del-retamar")
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["documents_checked"], 5)
            adapter.update_proyectos(out, Path(directory) / "state.json")
            self.assertEqual(len(out.read_text().splitlines()), 1)
            self.assertEqual(json.loads(out.read_text())["municipio"], "Santa Cruz del Retamar")
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), "")

    def test_document_failure_preserves_previous_output(self):
        for bad, error in ((True, False), (False, True)):
            with TemporaryDirectory() as directory, patch(
                "municipio.adapters.santa_cruz_del_retamar.requests.Session",
                return_value=self.session(bad, error),
            ):
                out = Path(directory) / "proyectos.jsonl"
                out.write_text("previous snapshot\n")
                adapter = SantaCruzDelRetamarAyuntamientoAdapter("santa-cruz-del-retamar")
                with self.assertRaises((ValueError, requests.HTTPError)):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), "previous snapshot\n")

    def test_manifest(self):
        manifest = load_manifest("santa-cruz-del-retamar")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "45157")
        self.assertEqual(manifest.provincia, "Toledo")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == "__main__":
    unittest.main()
