import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_llorenc_des_cardassar import (
    MUNICIPIO, SOURCES, SantLlorencDesCardassarAyuntamientoAdapter,
    parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.entity_policy import classify

SOURCE = SOURCES[0][0]
TITLE = f"113e/2025 MP núm. 19 NS de {MUNICIPIO}"
LINK = '<a href="contenido.do?idsite=7085&amp;cont=173087">{}</a>'
DOCS = '<a href="archivopub.do?ctrl=MCRST7085ZI519038&amp;id=519038">Memoria</a>'


def page(title, body):
    return f'<main><div class="imc--contenido-html"><h1>{title}</h1>{body}</div></main>'


def inventory(body=None):
    return page("Documents en avaluació simplificada", body if body is not None else LINK.format(TITLE))


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.item = parse_inventory(inventory(), SOURCE)[0]
        self.detail_url = self.item["url_descubrimiento"]

    def test_inventory_only_content_exact_municipality_and_strategic_records(self):
        body = LINK.format(TITLE) * 2 + LINK.format(TITLE.replace("113e/", "113a/"))
        body += LINK.format(TITLE.replace(MUNICIPIO, "Sant Llorenç de Morunys"))
        html = '<nav>' + LINK.format(TITLE.replace("113e/", "999e/")) + '</nav>' + inventory(body)
        rows = parse_inventory(html, SOURCE)
        self.assertEqual([r["expediente"] for r in rows], ["113e/2025"])
        self.assertIn('/publicacio_de_documents_', rows[0]["url_descubrimiento"])

    def test_documents_grouped_unknown_dates_and_title_discrepancy_retained(self):
        item = {**self.item, "titulo_inventario": TITLE.replace("19 NS", "9 NS")}
        html = page(TITLE, DOCS * 2 + DOCS.replace("519038", "519037").replace("Memoria", "Estudi Ambiental"))
        row = parse_detail(html, self.detail_url, item, SOURCE, "simplificada")
        self.assertEqual(len(row["documentos"]), 2)
        self.assertTrue(row["discrepancia_titulo"])
        self.assertIn("9 NS", row["titulo_inventario"])
        self.assertIn("19 NS", row["titulo"])
        for key in ("fecha", "fecha_publicacion", "fecha_acuerdo", "fecha_aprob", "lat", "lon", "geometry", "fase"):
            self.assertIsNone(row[key])
        self.assertEqual(row["codigo_ine"], "07051")
        self.assertEqual(classify(row)["entity_type"], "expediente")
        self.assertEqual(row["documentos"][0]["url_procedencia"], self.detail_url)

    def test_pagination_and_markup_changes_fail(self):
        for html in (inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory('<div class="pagination"><a href="?page=2">2</a></div>'),
                     inventory(LINK.format(TITLE) + '<a href="?page=2">Següent</a>'),
                     '<h1>Documents en avaluació simplificada</h1>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_conflicting_identity_or_source_fails(self):
        conflict = LINK.format(TITLE).replace('173087', '999999')
        for html in (inventory(LINK.format(TITLE) + conflict),
                     inventory(LINK.format(TITLE).replace('contenido.do', 'https://example.com/contenido.do'))):
            with self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)
        for title, docs in ((TITLE.replace('113e/', '999e/'), DOCS),
                            (TITLE.replace(MUNICIPIO, 'Palma'), DOCS), (TITLE, ''),
                            (TITLE, '<a href="/new-document-service">Memoria</a>')):
            with self.assertRaises(ValueError):
                parse_detail(page(title, docs), self.detail_url, self.item, SOURCE, "simplificada")

    def test_complete_refresh_uses_both_sources_and_preserves_output_on_failure(self):
        adapter = SantLlorencDesCardassarAyuntamientoAdapter("sant-llorenc-des-cardassar")
        ordinary = page("Documents en avaluació ordinària", "")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[(inventory(), SOURCE), (page(TITLE, DOCS), self.detail_url), (ordinary, SOURCES[1][0])]) as fetch, patch('municipio.adapters.sant_llorenc_des_cardassar.time.sleep'):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(result['rows'], 1)
                self.assertEqual(fetch.call_count, 3)
                self.assertEqual(json.loads(output.read_text())['expediente'], '113e/2025')
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', return_value=('<html>Error</html>', SOURCE)), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            with patch.object(adapter, '_fetch', return_value=(ordinary, SOURCE)), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            with patch.object(adapter, '_fetch', side_effect=AssertionError('licences must not fetch')):
                self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest_identity_and_disabled_automation(self):
        manifest = load_manifest('sant-llorenc-des-cardassar')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07051')
        self.assertEqual(manifest.nombre, MUNICIPIO)
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.sant_llorenc_des_cardassar:SantLlorencDesCardassarAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
