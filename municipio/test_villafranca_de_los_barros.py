"""Offline regression cases for the public DOE notice structure."""
import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.villafranca_de_los_barros import (
    PUBLISHER, VillafrancaDeLosBarrosAyuntamientoAdapter,
    group_notices, parse_inventory, parse_notice,
)
from municipio.manifest import load_manifest, load_yaml

URL = "https://doe.juntaex.es/otrosFormatos/html.php?xml=2026081420&anio=2026&doe=1620o"
NOTICE = f"""
<div class="Contenido_principal">
<div class="tablabordecolor">ANUNCIO de 4 de agosto de 2026 sobre aprobación inicial de la modificación puntual del Plan Parcial del Sector 5 de las Normas Subsidiarias de Planeamiento.</div>
<div class="tablaborde">
<span class="negrita">Fecha Publicación: </span>viernes, 21 de agosto de 2026<div></div>
<span class="negrita">Organismo: </span>{PUBLISHER}<div></div>
<a href="/pdfs/doe/2026/1620o/26081420.pdf">PDF</a>
<a href="/../pdfs/doe/2026/1620o/xml/2026081420.xml">XML</a>
</div>
<div class="xml"><div class="Txt">Aprobación inicial, si procede, de la modificación puntual del Plan Parcial del Sector 5.</div>
<div class="Txt">Previo Acuerdo de Pleno de esta corporación, en sesión celebrada con fecha 30 de julio de 2026, y mediante Resolución de la Alcaldía n.º 2026/1097, de fecha 4 de agosto de 2026, se procede a la modificación puntual del Plan Parcial del Sector 5 de las Normas Subsidiarias de Planeamiento para la supresión y posterior recalificación de viales como suelo industrial y medidas compensatorias para mantener la proporción y la calidad de las dotaciones públicas, según texto redactado por el Arquitecto municipal de fecha 21 de julio de 2026 (Expte. 2026/1/S871).</div>
</div></div>
"""


class VillafrancaParserTests(unittest.TestCase):
    def test_dates_and_instrument_not_announcement(self):
        notice = parse_notice(NOTICE, URL)
        self.assertEqual(notice["fecha_publicacion"], "2026-08-21")
        self.assertEqual(notice["fecha_acuerdo"], "2026-07-30")
        self.assertEqual(notice["fecha_resolucion"], "2026-08-04")
        self.assertEqual(notice["fecha_anuncio"], "2026-08-04")
        self.assertIsNone(notice["fecha_aprob"])
        self.assertTrue(notice["titulo"].startswith("modificación puntual del Plan Parcial"))
        self.assertNotIn("Previo Acuerdo", notice["titulo"])
        self.assertEqual(set(notice["formatos"]), {"html", "pdf", "xml"})

    def test_missing_agreement_is_not_publication_or_drafting_date(self):
        html = NOTICE.replace("sesión celebrada con fecha 30 de julio de 2026", "sesión celebrada")
        self.assertIsNone(parse_notice(html, URL)["fecha_acuerdo"])

    def test_wrong_municipality_and_non_projects_rejected(self):
        for html in (
            NOTICE.replace(PUBLISHER, "AYUNTAMIENTO DE VILLAFRANCA"),
            NOTICE.replace("sobre aprobación inicial", "sobre licitación"),
            NOTICE.replace("Expte. 2026/1/S871", "Formulario de solicitud"),
            "<a href='plan.pdf'>Solicitud de licencia urbanística</a>",
            NOTICE.replace("viernes, 21 de agosto de 2026", ""),
        ):
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                parse_notice(html, URL)

    def test_grouping_keeps_all_notices_and_stable_identity(self):
        notice = parse_notice(NOTICE, URL)
        previous = copy.deepcopy(notice)
        previous.update(url=URL + "&version=anterior", fecha_publicacion="2026-08-05")
        previous["formatos"]["html"] = previous["url"]
        rows = group_notices([notice, previous, notice])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["documentos"]), 2)
        self.assertEqual(rows[0]["id"], group_notices([previous])[0]["id"])
        self.assertEqual(rows[0]["fecha_publicacion"], "2026-08-21")
        self.assertIsNone(rows[0]["lat"])
        self.assertIsNone(rows[0]["geometry"])
        self.assertFalse(rows[0]["publication_ready"])

    def test_inventory_count_detects_truncation_and_changing_markup(self):
        html = f'<p>Resultado de la búsqueda: 1 disposición</p><a href="{URL}">HTML</a>'
        self.assertEqual(parse_inventory(html), [URL])
        with self.assertRaisesRegex(ValueError, "pagination"):
            parse_inventory(html.replace("1 disposición", "2 disposiciones"))
        with self.assertRaises(ValueError):
            parse_inventory("<form>Login</form>")
        with self.assertRaises(ValueError):
            parse_inventory(html.replace("doe.juntaex.es", "example.org"))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("villafranca-de-los-barros")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "06149")
        self.assertEqual(manifest.provincia, "Badajoz")
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "licencias.jsonl"
            result = VillafrancaDeLosBarrosAyuntamientoAdapter().backfill_licencias(target)
            self.assertTrue(result["disabled"])
            self.assertEqual(target.read_text(), "")


if __name__ == "__main__":
    unittest.main()
