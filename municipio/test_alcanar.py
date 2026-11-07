"""Offline parser regressions; no external requests or evidence files needed."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.alcanar import (
    AlcanarAyuntamientoAdapter, BASE, ajax_fragment, group_documents, parse_page,
)
from municipio.manifest import load_manifest


def notice(uid, title, procedure="Planejament General", expediente="1011/2026", publication="03/11/2026"):
    return f'''<tr><td class="class_name"><a href="{BASE}/preview-document/{uid}">{title}</a></td>
      <td class="class_folderCode">{expediente}</td><td class="class_folderName">{procedure}</td>
      <td class="class_description">{title}</td><td class="class_dateFrom">{publication}</td></tr>'''


A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"
C = "33333333-3333-3333-3333-333333333333"
TITLE = "Anunci aprovació provisional Modificació Puntual del Pla General d'Ordenació Urbana d'Alcanar relativa a les claus 17 i 19"


def page(rows, more=False):
    control = '''<button onclick="wicketAjaxGet('?x=opaque-token',null)">Veure'n més</button>''' if more else ""
    return f'<table class="AdvertisementBoardListPanel">{rows}</table><div class="more_results">{control}</div>'


class AlcanarTests(unittest.TestCase):
    def test_publication_is_not_approval_or_document_creation(self):
        _, docs, action = parse_page(page(notice(A, TITLE)), initial=True)
        row = group_documents(docs)[0]
        self.assertIsNone(action)
        self.assertEqual(row["fecha_publicacion"], "2026-11-03")
        self.assertEqual(row["fase"], "aprobación provisional")
        for field in ("fecha", "fecha_aprob", "fecha_acuerdo", "lat", "lon", "geometry"):
            self.assertIsNone(row[field])
        self.assertFalse(row["publication_ready"])

    def test_groups_instrument_across_pages_retaining_documents(self):
        _, first, action = parse_page(page(notice(A, TITLE), more=True), initial=True)
        self.assertEqual(action, "?x=opaque-token")
        xml = f'''<ajax-response><component id="rows"><![CDATA[{notice(B, TITLE, publication="04/11/2026")}]]></component>
        <component id="more"><![CDATA[<div id="more" style="display:none"></div>]]></component></ajax-response>'''
        _, second, action = parse_page(ajax_fragment(xml))
        self.assertIsNone(action)
        rows = group_documents(first + second + first)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["documentos"]), 2)
        self.assertEqual(rows[0]["fecha_publicacion"], "2026-11-04")
        self.assertEqual(rows[0]["id"], group_documents(second)[0]["id"])

    def test_excludes_procurement_forms_and_employment(self):
        html = page(notice(A, "Licitació d'obres", "Contractacions")
                    + notice(B, "Sol·licitud de llicència urbanística", "Llicències")
                    + notice(C, "Borsa TAE urbanisme", "Seleccions de Personal"))
        identities, docs, _ = parse_page(html, initial=True)
        self.assertEqual(len(identities), 3)
        self.assertEqual(docs, [])
        with self.assertRaises(ValueError):
            group_documents(docs)

    def test_special_plan_and_separate_expediente(self):
        title = "Anunci aprovació inicial Pla Especial urbanístic d'Ampliació de Reverter Indústries"
        _, docs, _ = parse_page(page(notice(A, TITLE) + notice(B, title,
            "Aprovació de Pla Especial Urbanístic (Aprovació per la Comissió Territorial d'Urbanisme)", "1584/2018")), initial=True)
        self.assertEqual(len(group_documents(docs)), 2)

    def test_rejects_login_missing_reference_and_bad_dates(self):
        for html in ("<h1>Identifica't</h1>", page(notice(A, TITLE, expediente="")),
                     page(notice(A, TITLE, publication="31/02/2026"))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, initial=True)

    def test_pagination_changes_fail_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            parse_page(page(notice(A, TITLE)).replace('<div class="more_results"></div>',
                       "<button>Veure'n més</button>"), initial=True)
        with self.assertRaises(ValueError):
            ajax_fragment(f"<ajax-response><component><![CDATA[{notice(A, TITLE)}]]></component></ajax-response>")
        with self.assertRaises(ValueError):
            ajax_fragment("<html>Session expired</html>")

    def test_rejects_unexpected_official_host(self):
        with self.assertRaises(ValueError):
            parse_page(page(notice(A, TITLE)).replace(BASE, "https://example.org"), initial=True)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("alcanar")
        self.assertEqual(manifest.provincia, "Tarragona")
        self.assertEqual(manifest.portal.config["ine_code"], "43004")
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "licencias.jsonl"
            self.assertEqual(AlcanarAyuntamientoAdapter().backfill_licencias(path)["status"], "disabled")
            self.assertEqual(path.read_text(), "")


if __name__ == "__main__":
    unittest.main()
