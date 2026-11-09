import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sotillo_de_la_adrada import (
    BASE, INVENTORY, SotilloDeLaAdradaAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest, load_yaml


TITLE = "Normas Urbanísticas Municipales de Sotillo de la Adrada"
URL = BASE + "/normas.html"


def inventory(*titles):
    return '<section id="seccion"><h1>Urbanismo</h1>' + ''.join(
        f'<a href="/{i}.html"><h6><i class="fa-arrow-circle-right"></i>{t}</h6></a>'
        for i, t in enumerate(titles)
    ) + '</section>'


def detail(title=TITLE, text="Texto y planos del instrumento.", docs=None):
    docs = docs if docs is not None else ["imagenes/archivos_adjuntos/plan.pdf"]
    return (f'<span>Creado el 16-09-2018 y actualizado el 01-04-2019</span>'
            f'<div class="noticia"><h1 class="titulo">{title}</h1>'
            f'<div id="cuerpo"><p>{text}</p></div></div><div class="contenedorarchivos">'
            + ''.join(f'<a href="{u}">Documento</a>' for u in docs) + '</div>')


class SotilloParserTests(unittest.TestCase):
    def test_inventory_filters_forms_regulations_and_unrelated_news(self):
        html = inventory(TITLE, "Estudio de detalle de Las Ventillas", "Modificación puntual 14",
                         "Declaración responsable de obras", "Normativa sectorial de urbanismo",
                         "Ordenanzas municipales de carácter urbanístico", "Anuncio de contratación")
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], (TITLE, BASE + "/0.html"))

    def test_group_all_documents_and_keep_provenance(self):
        docs = [f"imagenes/archivos_adjuntos/{i}.pdf" for i in range(10)]
        row = parse_project(detail(docs=docs + [docs[0]]), URL, TITLE)
        self.assertEqual(len(row["documentos"]), 10)
        self.assertEqual(row["documentos"][0]["url"], BASE + "/" + docs[0])
        self.assertEqual(row["documentos"][0]["source_page"], URL)
        self.assertEqual(row["id"], parse_project(detail(docs=list(reversed(docs))), URL, TITLE)["id"])

    def test_explicit_agreement_is_separate_from_publication_and_page_update(self):
        row = parse_project(detail(text="Normas aprobadas definitivamente por Acuerdo de 7 de febrero de 2019."), URL, TITLE)
        self.assertEqual(row["fecha_acuerdo"], "2019-02-07")
        self.assertEqual(row["fecha_aprob"], "2019-02-07")
        self.assertEqual(row["fase"], "aprobación definitiva")
        self.assertIsNone(row["fecha_publicacion"])
        self.assertIsNone(row["fecha"])

    def test_missing_dates_phase_and_geometry_are_not_invented(self):
        row = parse_project(detail(), URL, TITLE)
        for key in ["fecha_acuerdo", "fecha_aprob", "fecha_publicacion", "fase", "lat", "lon", "geometry"]:
            self.assertIsNone(row[key])
        self.assertFalse(row["publication_ready"])

    def test_changed_empty_or_untrusted_sources_fail(self):
        for html in ["<h1>Login</h1>", inventory("Declaración responsable de obras"),
                     inventory(TITLE).replace('/0.html', 'https://example.org/plan')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        for html in ["<h1>Login</h1>", detail(docs=[]), detail(title="Another plan"),
                     detail(docs=["https://example.org/plan.pdf"])]:
            with self.assertRaises(ValueError):
                parse_project(html, URL, TITLE)

    def test_pagination_is_never_silently_truncated(self):
        for pagination in ['<a rel="next" href="?page=2">2</a>',
                           '<a href="javascript:">Siguiente »</a>', '<div class="pagination">2</div>']:
            with self.assertRaisesRegex(ValueError, "Pagination"):
                parse_inventory(inventory(TITLE).replace('</section>', pagination + '</section>'))

    def test_snapshot_update_and_disabled_licences(self):
        adapter = SotilloDeLaAdradaAyuntamientoAdapter("sotillo-de-la-adrada")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('old record\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(TITLE), detail()]):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '05240')
            self.assertFalse((Path(tmp) / 'state.json').exists())
            lic = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('sotillo-de-la-adrada')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '05240')
        self.assertEqual(manifest.provincia, 'Ávila')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
