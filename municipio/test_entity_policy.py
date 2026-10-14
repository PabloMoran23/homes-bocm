import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.entity_policy import POLICY_KEY, annotate, annotate_jsonl, classify, content_hash


class EntityPolicyTest(unittest.TestCase):
    def test_generic_catalog_form(self):
        for title in ("Solicitud de aprobación de planeamiento", "Formulario de licencia de obras", "Impreso de obras"):
            result = classify({"titulo": title, "url": "https://sede.example/catalog/obras"})
            self.assertEqual(result["entity_type"], "tramite_reutilizable")
            self.assertFalse(result["activity_eligible"])

    def test_catalog_is_not_universal_veto(self):
        result = classify({"titulo": "Plan parcial Sector 12", "expediente": "2026/123", "url": "https://sede.example/catalog/expediente/123"})
        self.assertTrue(result["activity_eligible"])
        self.assertEqual(result["entity_type"], "expediente")

    def test_outside_domain_versioned_categories(self):
        for title in ("Licencia de taxi", "Tenencia de animales potencialmente peligrosos", "Bolsa de empleo"):
            result = classify({"titulo": title, "expediente": "2026/12", "url": "https://example/12", "estado": "concedida"}, kind="licencia")
            self.assertFalse(result["activity_eligible"])
            self.assertTrue(result["reason_code"].startswith("outside_domain:"))

    def test_reference_requires_provenance_and_urban_evidence(self):
        for record in ({"titulo": "Obras de viviendas", "expediente": "2026/12"},
                       {"titulo": "Cambio de titular de comercio", "expediente": "2026/12", "url": "https://example/12"},
                       {"titulo": "Obras de viviendas", "expediente": "sin expediente", "url": "https://example/12"}):
            self.assertFalse(classify(record)["activity_eligible"])

    def test_resources_and_unknown_stay_available(self):
        for title, url, entity in (("Ordenanza urbanística", "https://example/reg", "normativa"),
                                    ("Plano P4", "https://example/plano.pdf", "documento"),
                                    ("Anuncio de planeamiento", "https://example/notice", "anuncio"),
                                    ("Planeamiento", "https://example/catalog/x", "pendiente")):
            rec = {"titulo": title, "url": url, "pdf_urls": [url], "_semantic_contract": {"original": "kept"}}
            annotated = annotate(rec)
            self.assertEqual(annotated[POLICY_KEY]["entity_type"], entity)
            self.assertEqual({k: v for k, v in annotated.items() if k != POLICY_KEY}, rec)

    def test_concession_requires_act_or_status_not_generic_date(self):
        rec = {"titulo": "Licencia de obras de viviendas", "expediente": "2026/12", "url": "https://example/12", "fecha": "2026-10-14"}
        self.assertFalse(classify(rec, kind="licencia")["activity_eligible"])
        self.assertFalse(classify({**rec, "fecha_concesion": "invalid"}, kind="licencia")["activity_eligible"])
        self.assertTrue(classify({**rec, "estado": "concedida"}, kind="licencia")["activity_eligible"])
        self.assertTrue(classify({**rec, "fecha_concesion": "2026-10-14"}, kind="licencia")["grant_evidenced"])

    def test_denied_requested_revoked_and_conflicting_grants_abstain(self):
        common = {"expediente": "2026/123", "url": "https://sede.example/exp/123"}
        for title, state in (
            ("Denegación de concesión de licencia de obras", "denegada"),
            ("Solicitud de concesión de licencia de obras", "solicitada"),
            ("Revocación de licencia de obras concedida", "revocada"),
            ("No se concede licencia de obras", ""),
            ("Se concede licencia de obras", "denegada"),
            ("Solicitud de licencia de obras", "concedida"),
            ("Propuesta de concesión de licencia de obras", "pendiente"),
            ("Concesión de licencia de obras", ""),
        ):
            rec = {**common, "titulo": title, "estado": state}
            result = classify(rec, kind="licencia")
            self.assertFalse(result["grant_evidenced"], (title, state))
            self.assertFalse(result["activity_eligible"], (title, state))
            if state in ("denegada", "solicitada", "revocada"):
                self.assertFalse(classify({**rec, "fecha_concesion": "2026-10-01"}, kind="licencia")["grant_evidenced"])
        for evidence in ({"estado": "concedida"}, {"fecha_concesion": "2026-10-01"}, {}):
            self.assertTrue(classify({**common, "titulo": "Se concede licencia de obras", **evidence}, kind="licencia")["grant_evidenced"])

    def test_official_source_structures(self):
        self.assertTrue(classify({"titulo": "Área A", "object_id": 123, "sigma_layer_kind": "gestion", "url": "https://geoportal.example/123"})["activity_eligible"])
        self.assertTrue(classify({"titulo": "Construcción vivienda", "source": "madrid-opendata", "licencia_key": "stable", "fecha_concesion": "2026-10-01"}, kind="licencia")["activity_eligible"])

    def test_identified_published_act_is_an_activity(self):
        rec = {"titulo": "Aprobación definitiva del Plan General", "municipio": "Madrid", "source": "bocm", "url": "https://www.bocm.es/boletin.pdf"}
        self.assertTrue(classify(rec)["activity_eligible"])
        self.assertEqual(classify(rec)["entity_type"], "actuacion")
        self.assertFalse(classify({**rec, "url": "https://sede.example/catalog/x"})["activity_eligible"])

    def test_recurrence_content_and_rule_changes(self):
        rec = {"titulo": "Formulario de obras", "url": "https://example/catalog/x"}
        once = annotate(rec)
        self.assertEqual(annotate(once), once)
        self.assertEqual(content_hash(rec), content_hash(once))
        self.assertEqual(content_hash(rec), content_hash({**once, "_semantic_contract": {"changed": True}}))
        changed = annotate({**once, "titulo": "Plan parcial Sector 12", "expediente": "2026/12"})
        self.assertTrue(changed[POLICY_KEY]["activity_eligible"])
        with patch("municipio.entity_policy.POLICY_VERSION", "next"):
            self.assertEqual(annotate(once)[POLICY_KEY]["version"], "next")

    def test_blind_review_does_not_claim_precision_without_complete_labels(self):
        from db.audit_entity_activity import evaluate
        with self.assertRaises(ValueError):
            evaluate([{"identifiable_activity": None, "generic_form": None}] * 200)
        with self.assertRaises(ValueError):
            evaluate([{"identifiable_activity": True, "generic_form": False}] * 199)
        self.assertTrue(evaluate([{"identifiable_activity": True, "generic_form": False}] * 200)["passes"])
        self.assertFalse(evaluate([{"identifiable_activity": True, "generic_form": False}] * 199 + [{"identifiable_activity": False, "generic_form": True}])["passes"])

    def test_adapter_annotation_and_unknown_incident(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "proyectos.jsonl"
            path.write_text(''.join(json.dumps({"id": str(i), "titulo": "Planeamiento"}) + '\n' for i in range(12)))
            result = annotate_jsonl(path, kind="proyecto")
            self.assertEqual(result["status"], "adapter_incident")
            previous = path.read_bytes()
            annotate_jsonl(path, kind="proyecto")
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(len(path.read_text().splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
