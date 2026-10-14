import unittest
from unittest.mock import patch

from project_semantics import derive
from ingest import portal_proyecto_row, save_proyectos


class ContractTest(unittest.TestCase):
    def test_actual_adapter_description_aliases(self):
        for alias in ("descripcion", "resumen", "resumen_contenido"):
            with self.subTest(alias=alias):
                d = derive({"titulo": "Plan Norte", alias: "Documento de ordenación del ámbito Norte", "url": "https://example.test/1"})
                self.assertEqual(d["description"]["evidence"]["field"], alias)
                self.assertEqual(d["description"]["evidence"]["url"], "https://example.test/1")
                self.assertIsNone(d["summary"])

    def test_title_only_does_not_become_summary(self):
        row = portal_proyecto_row({"id": "1", "titulo": "Plan Norte", "resumen": "Plan Norte"}, slug="parla", nombre="Parla")
        self.assertIsNone(row["resumen_contenido"])
        self.assertIsNone(row["bocm_resumen"])
        self.assertIn("_entity_policy", row["raw_features_json"].adapted)
        self.assertEqual(row["raw_features_json"].adapted["_semantic_contract"]["status"], "discovered")

    def test_generic_date_type_and_fake_phase_not_inferred(self):
        for phase in (None, "Plan parcial"):
            d = derive({"tipo": "Plan parcial", "fase": phase, "fecha": "2026-10-14"})
            self.assertIsNone(d["fase"])
            self.assertIsNone(d["fecha_aprob"])
            self.assertIsNone(d["fecha_publicacion"])
            self.assertIn("fecha", d["unknown"])

    def test_explicit_dates_and_each_claim_cites_original_field(self):
        rec = {"tipo": "Plan parcial", "fase": "Aprobación inicial", "fecha_publicacion": "2026-10-14", "fecha_acuerdo": "2026-10-01", "url": "https://example.test/1", "descripcion": "420 viviendas"}
        d = derive(rec)
        self.assertIsNone(d["fecha_aprob"])
        self.assertEqual(d["fase_normalizada"], "aprobacion_inicial")
        self.assertNotIn("420", d["summary"])
        for name in d["summary_facts"]:
            fact = next(f for f in d["facts"] if f["name"] == name)
            self.assertEqual(rec[fact["evidence"]["field"]], fact["value"])

    def test_ambiguity_and_invalid_date_recovery(self):
        rec = {"fase": "Plan parcial", "fecha_publicacion": "2026-02-30", "fecha_acuerdo": "2026-01-01", "bocm_fecha_acuerdo": "2026-02-01"}
        d = derive(rec)
        self.assertEqual(d["unknown"]["fecha_acuerdo"], "conflicting_aliases")
        self.assertIsNone(d["fecha_publicacion"])
        rec.update(fase="Información pública", fecha_publicacion="2026-02-28", bocm_fecha_acuerdo="2026-01-01")
        recovered = derive(rec)
        self.assertEqual(recovered["fecha_publicacion"], "2026-02-28")
        self.assertEqual(recovered["fecha_acuerdo"], "2026-01-01")

    def test_deterministic_repeated_changed_document_and_rule(self):
        rec = {"titulo": "Plan", "pdf_url": "https://example.test/v1.pdf"}
        first = derive(rec)
        self.assertEqual(first, derive(rec))
        rec["pdf_url"] = "https://example.test/v2.pdf"
        self.assertNotEqual(first["source_hash"], derive(rec)["source_hash"])
        with patch("project_semantics.TEMPLATE_VERSION", "test/2"):
            self.assertNotEqual(first["template_version"], derive(rec)["template_version"])

    def test_export_preserves_unknown_semantics_without_legacy_fallback(self):
        from export_web_data_from_supabase import proyecto_to_portal
        d = derive({"titulo": "Plan", "fecha": "2026-10-14"})
        output = proyecto_to_portal({"raw_features_json": {"_semantic_contract": d},
                                    "bocm_fecha_acuerdo": "2026-10-14", "bocm_estado_tramitacion": "Plan parcial"})
        self.assertIsNone(output["fechaAcuerdo"])
        self.assertEqual(output["estadoTramitacion"], "")
        self.assertEqual(output["contenidoEstado"], "discovered")
        self.assertIn("descripcion", output["contenidoDesconocido"])

    def test_other_guards_preserved_without_invalidating_content_hash(self):
        original = {"titulo": "Plan", "tipo": "Plan parcial"}
        self.assertEqual(derive(original)["source_hash"], derive({**original, "_entity_policy": {"version": 2}})["source_hash"])

    def test_combined_geography_semantics_guards_preserve_quarantine_and_other_markers(self):
        quarantine = {"status": "quarantined", "original": {"lat": 4000000, "lng": 400000}}
        raw = {"titulo": "Plan Norte", "tipo": "Plan parcial", "fase": "Información pública",
               "_geography_quarantine": quarantine, "_entity_policy": {"status": "retained"},
               "_territory": {"scope": "municipal"}}
        source = {"id": "quarantined:1", "municipio_slug": "unknown", "municipio": "Test",
                  "fuente": "ayuntamiento", "raw_features_json": raw}
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, *args): pass
        class Connection:
            def cursor(self): return Cursor()
        from ingest import _PROYECTO_UPSERT_COLS
        with patch("ingest.execute_values") as execute, patch("ingest.ensure_schema"), patch("ingest._classify_saved"):
            save_proyectos([source], conn=Connection())
        values = dict(zip(_PROYECTO_UPSERT_COLS, execute.call_args_list[0].args[2][0]))
        saved = values["raw_features_json"].adapted
        self.assertEqual(saved["_geography_quarantine"], quarantine)
        self.assertEqual(saved["_entity_policy"], raw["_entity_policy"])
        self.assertEqual(saved["_territory"], raw["_territory"])
        self.assertEqual(saved["_semantic_contract"]["fase_normalizada"], "informacion_publica")
        self.assertEqual(saved["geography_validation"]["status"], "quarantined")
        self.assertIsNone(values["lat"])
        self.assertIsNone(values["lng"])

    def test_upsert_clears_bad_history_and_persists_immutable_evidence(self):
        row = portal_proyecto_row({"id": "1", "titulo": "Plan", "fecha": "2026-01-01"}, slug="parla", nombre="Parla")
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, *args): pass
        class Connection:
            def cursor(self): return Cursor()
        with patch("ingest.execute_values") as execute, patch("ingest.ensure_schema"), patch("ingest._classify_saved"):
            self.assertEqual(save_proyectos([row], conn=Connection()), 1)
        sql = execute.call_args_list[0].args[1]
        self.assertIn("fecha_aprob = CASE WHEN EXCLUDED.raw_features_json ? '_semantic_contract'", sql)
        self.assertIn("ON CONFLICT DO NOTHING", execute.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
