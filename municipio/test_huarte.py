import unittest
from unittest.mock import patch

from municipio.adapters.huarte import HuarteAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml


def notice(identifier=9121, published="2021-10-29T10:30:00", scope="C/ Zubiarte 16"):
    return {
        "id": identifier, "date": published,
        "link": "https://huarte.es/noticias/plan-" + str(identifier) + "/",
        "title": {"rendered": "Proceso de participación &#8211; Plan Especial Actuación Urbana. " + scope},
        "content": {"rendered": '<p>Proceso de participación pública previo a aprobación inicial, '
                   'cuyo avance adjuntamos.</p><a href="/wp-content/uploads/docs/plan.pdf">Documento</a>'
                   '<a href="/wp-content/uploads/docs/reunion.pdf">Reunión</a>'},
    }


class Response:
    def __init__(self, data, total, pages):
        self.data = data
        self.headers = {"X-WP-Total": str(total), "X-WP-TotalPages": str(pages)}

    def json(self):
        return self.data


class HuarteTests(unittest.TestCase):
    def test_group_instrument_preserve_dates_documents_and_provenance(self):
        early = notice()
        later = notice(5233, "2022-10-21T10:04:00")
        later["content"]["rendered"] += '<a href="/wp-content/uploads/docs/revised.pdf">Documento</a>'
        records = HuarteAyuntamientoAdapter.parse_posts([later, early])
        self.assertEqual(len(records), 1)
        row = records[0]
        self.assertEqual(row["fecha_publicacion"], "2021-10-29")
        self.assertIsNone(row["fecha_aprob"])
        self.assertIsNone(row["fecha_acuerdo"])
        self.assertIsNone(row["geometry"])
        self.assertEqual(len(row["publicaciones"]), 2)
        self.assertEqual(len(row["documentos"]), 3)
        self.assertEqual(len(row["documentos"][0]["procedencias"]), 2)
        self.assertEqual(row["id"], HuarteAyuntamientoAdapter.parse_posts([early])[0]["id"])

    def test_reject_forms_news_and_missing_technical_document(self):
        unrelated = notice(99)
        unrelated["title"]["rendered"] = "Solicitud de licencia de obras / anuncio de contratación"
        self.assertEqual(len(HuarteAyuntamientoAdapter.parse_posts([notice(), unrelated])), 1)
        for content in ("", '<p>cuyo avance adjuntamos</p><a href="/wp-content/uploads/a.pdf">Reunión</a>',
                        '<p>cuyo avance adjuntamos</p><a href="https://other.example/a.pdf">Documento</a>'):
            invalid = notice()
            invalid["content"]["rendered"] = content
            with self.assertRaises(ValueError):
                HuarteAyuntamientoAdapter.parse_posts([invalid])
        with self.assertRaises(ValueError):
            HuarteAyuntamientoAdapter.parse_posts([unrelated])

    def test_barrio_is_modification_despite_template_title(self):
        row = HuarteAyuntamientoAdapter.parse_posts([notice(scope="Barrio Antigüo")])[0]
        self.assertEqual(row["tipo"], "modificacion_planeamiento")

    def test_walk_all_pages_and_fail_incomplete_or_changing_inventory(self):
        adapter = HuarteAyuntamientoAdapter("huarte")
        responses = [Response([notice()], 2, 2), Response([notice(5233)], 2, 2)]
        with patch.object(adapter, "_get", side_effect=responses) as get:
            self.assertEqual(len(adapter._inventory()), 2)
            self.assertEqual(get.call_args_list[1].args[1]["page"], 2)
        for responses in (
            [Response([notice()], 2, 1)],
            [Response([notice()], 2, 2), Response([], 2, 2)],
            [Response([notice()], 2, 2), Response([notice()], 2, 2)],
            [Response([notice()], 2, 2), Response([notice(5233)], 3, 2)],
        ):
            with patch.object(adapter, "_get", side_effect=responses), self.assertRaises(ValueError):
                adapter._inventory()

    def test_manifest_contract(self):
        manifest = load_manifest("huarte")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "31122")
        self.assertEqual(manifest.provincia, "Navarra")
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])


if __name__ == "__main__":
    unittest.main()
