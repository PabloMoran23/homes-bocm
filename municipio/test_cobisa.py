import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.cobisa import CobisaAyuntamientoAdapter, SOURCE, parse_post
from municipio.manifest import load_manifest, load_yaml


def work():
    return {"id": 1476, "status": "publish", "type": "post",
            "link": "https://cobisa.es/cobisa-amplio-las-gradas-del-polideportivo-municipal/",
            "date": "2026-08-25T12:18:02", "modified": "2026-09-01T13:28:58",
            "title": {"rendered": "Cobisa amplió las gradas del polideportivo municipal"},
            "content": {"rendered": "<p>El Ayuntamiento de Cobisa llevó a cabo la ampliación "
                       "del graderío del polideportivo municipal.</p>"}}


def response(posts, pages=1, total=1):
    result = Mock(url=SOURCE, headers={"X-WP-TotalPages": str(pages), "X-WP-Total": str(total)})
    result.json.return_value = posts
    return result


class CobisaTests(unittest.TestCase):
    def test_physical_work_and_date_provenance(self):
        row = parse_post(work())
        self.assertEqual(row["codigo_ine"], "45052")
        self.assertEqual(row["fecha_publicacion"], "2026-08-25")
        self.assertIn("llevó a cabo", row["descripcion"])
        self.assertFalse(row["publication_ready"])
        for key in ("fecha", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "fase"):
            self.assertNotIn(key, row)

    def test_excludes_forms_procurement_events_and_unsubstantiated_work(self):
        for title, body in [
            ("LICITACION DE PARCELAS MUNICIPALES", "informacion adicional y modelos"),
            ("Solicitud de licencia para reforma del polideportivo", "Formulario"),
            ("OBRA TEATRAL: UN CRIMEN CASI PERFECTO", ""),
            ("Cobisa ampliará las gradas del polideportivo", "Propuesta futura"),
            ("Cobisa amplió las gradas del polideportivo municipal", "Solo un titular"),
        ]:
            post = work()
            post["title"]["rendered"], post["content"]["rendered"] = title, body
            with self.subTest(title=title):
                self.assertIsNone(parse_post(post))

    def test_groups_attached_documents_without_duplicate_records(self):
        post = work()
        post["content"]["rendered"] += ('<a href="/docs/gradas.pdf">Memoria</a>'
                                        '<a href="/docs/gradas.pdf">Otra copia</a>')
        row = parse_post(post)
        self.assertEqual(len(row["documentos"]), 2)
        self.assertEqual(row["documentos"][1]["url"], "https://cobisa.es/docs/gradas.pdf")
        post["link"] = "https://example.com/fake"
        with self.assertRaises(ValueError):
            parse_post(post)

    def run_inventory(self, responses, path):
        with patch("municipio.adapters.cobisa.requests.Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.get.side_effect = responses
            result = CobisaAyuntamientoAdapter("cobisa").backfill_proyectos(path)
            return result, session.get.call_args_list

    def test_visits_every_advertised_page(self):
        unrelated = copy.deepcopy(work())
        unrelated.update(id=1727, title={"rendered": "INAUGURACION EXPOSICION"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proyectos.jsonl"
            stats, calls = self.run_inventory([
                response([unrelated], pages=2, total=2),
                response([work()], pages=2, total=2)], path)
            self.assertEqual(stats["count"], 1)
            self.assertEqual(stats["inventory_posts"], 2)
            self.assertEqual([c.kwargs["params"]["page"] for c in calls], [1, 2])
            self.assertEqual(json.loads(path.read_text())["id"], "cobisa-obra-wp-1476")

    def test_incomplete_changing_duplicate_or_empty_inventory_fails_atomically(self):
        cases = [
            [response([work()], total=2)],
            [response([work()], pages=2, total=2), response([work()], pages=2, total=2)],
            [response([work()], pages=2, total=2), response([work()], pages=3, total=3)],
            [response([], pages=0, total=0)],
            [response([{**work(), "title": {"rendered": "Evento"}}])],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proyectos.jsonl"
            path.write_text("previous output")
            for responses in cases:
                with self.subTest(responses=responses), self.assertRaises(ValueError):
                    self.run_inventory(responses, path)
                self.assertEqual(path.read_text(), "previous output")

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("cobisa")
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw["codigo_ine"]),
                         ("Cobisa", "Toledo", "45052"))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "licencias.jsonl"
            self.assertTrue(CobisaAyuntamientoAdapter("cobisa").backfill_licencias(path)["disabled"])
            self.assertEqual(path.read_text(), "")


if __name__ == "__main__":
    unittest.main()
