"""Regresiones de la resolución territorial: no confundir municipios homónimos."""
import unittest
from collections import defaultdict

from export_project_directory import exclusion_reason, names, territory


class TerritoryTest(unittest.TestCase):
    def setUp(self):
        self.reference = [
            {"mun_name": "El Molar", "prov_name": "Madrid"},
            {"mun_name": "El Molar", "prov_name": "Tarragona"},
            {"mun_name": "Elx", "prov_name": "Alacant"},
            {"mun_name": "Madrid", "prov_name": "Madrid"},
        ]
        self.lookup = defaultdict(set)
        for i, row in enumerate(self.reference):
            for name in names(row["mun_name"]):
                self.lookup[name].add(i)

    def resolve(self, **row):
        return territory(row, self.reference, self.lookup)

    def test_ambiguous_name_is_not_guessed(self):
        self.assertIsNone(self.resolve(municipio="El Molar"))

    def test_province_embedded_in_source_label(self):
        self.assertEqual(self.resolve(municipio="El Molar", provincia="El Molar, Madrid")["prov_name"], "Madrid")

    def test_bilingual_alias(self):
        self.assertEqual(self.resolve(municipio="Elche")["mun_name"], "Elx")

    def test_sigma_with_missing_municipality(self):
        self.assertEqual(self.resolve(expediente_grupo="135/2024/00164")["mun_name"], "Madrid")

    def test_unresolved_joint_municipality_is_not_guessed(self):
        self.assertIsNone(self.resolve(municipio="El Molar y Madrid"))

    def test_municipal_news_is_not_a_project(self):
        for title in ["Alta en el Registro de Animales", "El Molar celebra La Maya en la Plaza Mayor", "Modificación del Calendario Fiscal"]:
            self.assertIsNotNone(exclusion_reason({"fuente": "ayuntamiento"}, title))

    def test_planning_pdf_is_retained(self):
        self.assertIsNone(exclusion_reason({"fuente": "ayuntamiento"}, "Plan de reforma interior Zona Mercado: anuncio.pdf"))

    def test_research_overrides_title_heuristic(self):
        self.assertIsNone(exclusion_reason({"fuente": "ayuntamiento", "investigado": True}, "Los Altozanos"))

    def test_short_planning_codes_are_not_discarded(self):
        for title in ["SU-NC-2 (SU-NC-2)", "Residencial 3 (UBZR3)", "PLANO P-4 ALTIMETRIA HOJA 3-4 PP-6"]:
            self.assertIsNone(exclusion_reason({"fuente": "ayuntamiento"}, title))


if __name__ == "__main__":
    unittest.main()
