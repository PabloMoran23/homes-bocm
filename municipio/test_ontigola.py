import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.ontigola import (
    BASE, SOURCE, OntigolaAyuntamientoAdapter, group_notices, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def card(title, slug="test", date="08/07/2021", population="Ontígola", docs=None):
    docs = docs if docs is not None else [slug]
    pop = f'<div class="field--name-field-poblacion">{population}</div>' if population else ""
    links = "".join(f'<a class="file-download" href="/sites/default/files/expedientes/{d}.pdf"><span class="file--title">{d}.pdf</span></a>' for d in docs)
    return f'''<article class="node" about="/urbanismo/acuerdos/{slug}">
    <h3 class="article__title">{title}</h3>{pop}
    <div class="field--name-field-expediente-fecha">{date}</div>
    <div class="field--name-field-expediente-fichero">{links}</div></article>'''


def page(cards, total=1, next_url=None):
    pager = f'<li class="pager__item--next"><a rel="next" href="{next_url}">Siguiente</a></li>' if next_url else ""
    return f'''<div class="view-buscador-expedientes"><div class="view-header">Mostrando 1 - 1 de {total} expediente/s encontrados</div><div class="view-content">{cards}</div>{pager}</div>'''


def response(html, url=SOURCE):
    return Mock(text=html, url=url, raise_for_status=Mock())


class OntigolaTests(unittest.TestCase):
    def test_groups_same_instrument_retains_dates_and_all_links(self):
        html = page(card("CPOTU Toledo MP1 PP ALBARDIALES III Art.38 TR, en ONTÍGOLA", "cpotu", "20/12/2021") +
                    card("CCI Toledo Modificación Puntual número 1 del Plan Parcial Los Albardiales III de las Normas Subsidiarias de Ontígola", "cci", docs=["cci", "anexo"]) +
                    card("CPOTU Toledo Modificacion Puntual nº 1 del Plan Parcial de Dehesa de la Plata I de Ontigola", "dehesa"), 3)
        rows = group_notices(parse_page(html, SOURCE)[0])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]["documentos"]), 3)
        self.assertEqual({a["fecha_acuerdo"] for a in rows[0]["acuerdos"]}, {"2021-07-08", "2021-12-20"})
        self.assertNotIn("fecha_acuerdo", rows[0])
        self.assertEqual(len(rows[1]["documentos"]), 1)
        for row in rows:
            self.assertFalse(row["publication_ready"])
            self.assertEqual(row["codigo_ine"], "45123")
            for field in ("fecha_aprob", "fecha_publicacion", "lat", "lon", "fase"):
                self.assertNotIn(field, row)

    def test_missing_population_can_use_explicit_title(self):
        notices, _, _ = parse_page(page(card("CROTU_RES.PAU Subarea 1.5.2_Ontigola", population=None)), SOURCE)
        self.assertEqual(len(group_notices(notices)), 1)

    def test_excludes_forms_procurement_and_unrelated_news(self):
        for title in ("Formulario de licencia de Ontígola", "Licitación de obras de Ontígola",
                      "Licitación del proyecto de urbanización de Ontígola",
                      "Modelo de solicitud del proyecto de Ontígola", "Fiestas de Ontígola"):
            with self.assertRaisesRegex(ValueError, "No supported"):
                group_notices(parse_page(page(card(title)), SOURCE)[0])

    def test_fails_on_missing_documents_wrong_municipality_and_drift(self):
        for html in ("<html>Challenge</html>", page(card("Proyecto de Ontígola", docs=[])),
                     page(card("Proyecto de Ontígola", population="Ocaña")), page(card("Proyecto de Ocaña"))):
            with self.assertRaises(ValueError):
                parse_page(html, SOURCE)

    @patch("municipio.adapters.ontigola.requests.get")
    def test_crawls_every_page_before_writing(self, get):
        next_url = SOURCE + "&page=1"
        get.side_effect = [response(page(card("Proyecto Centro Logístico de Ontígola", "logistico"), 2, next_url)),
                           response(page(card("Calificación Planta Solar Fotovoltaica Tagus 1 de Ontígola", "solar"), 2), next_url)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proyectos.jsonl"
            result = OntigolaAyuntamientoAdapter("ontigola").backfill_proyectos(out)
            self.assertEqual(result["source_notices"], 2)
            self.assertEqual(len(out.read_text().splitlines()), 2)
            self.assertEqual(get.call_count, 2)

    @patch("municipio.adapters.ontigola.requests.get")
    def test_incomplete_or_cyclic_pagination_preserves_output(self, get):
        for next_url in (None, SOURCE, BASE + "/acuerdos-expedientes?page=1"):
            get.return_value = response(page(card("Proyecto de Ontígola"), 2, next_url))
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "proyectos.jsonl"
                out.write_text("previous snapshot")
                with self.assertRaises(ValueError):
                    OntigolaAyuntamientoAdapter("ontigola").backfill_proyectos(out)
                self.assertEqual(out.read_text(), "previous snapshot")

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("ontigola")
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw["codigo_ine"]), ("Ontígola", "Toledo", "45123"))
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "licencias.jsonl"
            self.assertTrue(OntigolaAyuntamientoAdapter("ontigola").backfill_licencias(out)["disabled"])
            self.assertEqual(out.read_text(), "")


if __name__ == "__main__":
    unittest.main()
