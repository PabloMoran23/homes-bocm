import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.bergara import BergaraAyuntamientoAdapter, SOURCE, agreement_date
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def inventory(links, extra=""):
    return '<article><div id="book-navigation-517"><ul class="menu">' + ''.join(
        f'<li><a href="/es/node/{node}">{title}</a></li>' for node, title in links
    ) + '</ul><a class="page-next" href="/es/node/615">Noticias</a></div></article>' + extra


def chapter(title, fields="", children=""):
    return (f'<article class="node-book"><span property="dc:title" content="{title}"></span>'
            f'<div class="field field-name-body">{fields}</div>'
            f'<div class="book-navigation">{children}'
            '<a class="page-next" href="/es/node/999">Sibling</a></div></article>')


class BergaraParserTests(unittest.TestCase):
    def test_inventory_is_scoped_deduplicated_and_excludes_non_projects(self):
        html = inventory([
            (1, "Estudio de Detalle Parcelas 2 y 3 del Área 44"),
            (1, "Estudio de Detalle Parcelas 2 y 3 del Área 44"),
            (2, "Desestimiento de la tramitación de aprobación del estudio de detalle"),
            (3, "Convocatoria para la explotación de la cantina de Gorla"),
            (4, "Solicitud de licencia de obras"),
            (5, "Noticias"),
        ]) + '<a href="/es/node/666">Plan Especial ajeno al índice</a>'
        entries = BergaraAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["url"], "https://www.bergara.eus/es/node/1")

    def test_dates_are_decree_dates_not_signature_or_publication(self):
        text = ("El Alcalde mediante Decreto de 23 de septiembre de 2021 ha adoptado el siguiente acuerdo. "
                "Bergara, 24 de septiembre de 2021. BOG 30 de septiembre de 2021.")
        self.assertEqual(agreement_date(text), "2021-09-23")
        self.assertIsNone(agreement_date("BOG 30 de septiembre de 2021"))
        self.assertIsNone(agreement_date(text + " mediante Decreto de 1 de octubre de 2021"))
        self.assertIsNone(agreement_date("mediante Decreto de 2I de abril de 2022"))

    def test_documents_keep_provenance_and_child_chapters_not_siblings(self):
        html = chapter("Plan", '''<a href="/sites/default/files/plan.pdf">Memoria</a>
            <a href="https://www.bergara.eus/sites/default/files/plan.pdf">Adjunto</a>
            <a href="https://egoitza.gipuzkoa.eus/gao-bog/castell/bog/2024/01/15/c2400076.htm">BOG</a>
            <a href="/es/user/login">Login</a>''',
            '<ul class="menu"><li><a href="/es/node/2">Planos</a></li></ul>')
        page = BergaraAyuntamientoAdapter.parse_detail(html, SOURCE)
        self.assertEqual(len(page["documentos"]), 2)
        self.assertEqual(page["documentos"][0]["titulos"], ["Memoria", "Adjunto"])
        self.assertEqual(page["documentos"][0]["source_urls"], [SOURCE])
        self.assertEqual(page["children"], ["https://www.bergara.eus/es/node/2"])
        self.assertIsNone(page["fecha_publicacion"])
        related = BergaraAyuntamientoAdapter.parse_detail(chapter(
            "Estudio de detalle de la parcela H",
            '<a href="/sites/default/files/mod.punt_est._detalle_parcelas_d-e-f_y_g_larramendi_marzo_2021.pdf">Otros planos</a>'
        ), SOURCE)
        self.assertEqual(related["documentos"][0]["relacion"],
                         "adjunto_de_otras_parcelas_no_identificado_como_instrumento_h")

    def test_fail_closed_on_missing_inventory_or_pagination(self):
        for html in ["<html>Service unavailable</html>", inventory([]),
                     inventory([(1, "Plan Especial A")], '<ul class="pager"><li><a href="?page=1">2</a></li></ul>')]:
            with self.assertRaises(ValueError):
                BergaraAyuntamientoAdapter.parse_inventory(html)

    def test_full_snapshot_groups_a18_and_preserves_all_children(self):
        urls = {SOURCE: inventory([(19972, "Plan Especial de Ordenación Urbana Área A-18"),
                                   (20827, "Plan Especial de Ordenación Urbana modificado y adaptado del Área A-18")]),
                "https://www.bergara.eus/es/node/19972": chapter("A18", '<a href="/sites/default/files/initial.pdf">Initial</a>', '<ul class="menu"><li><a href="/es/node/7">Planos</a></li></ul>'),
                "https://www.bergara.eus/es/node/20827": chapter("A18 modificado", '<a href="/sites/default/files/final.pdf">Final</a>'),
                "https://www.bergara.eus/es/node/7": chapter("Planos", '<a href="/sites/default/files/map.pdf">Plano</a>')}

        class Response:
            headers = {"Content-Type": "text/html"}
            def __init__(self, url):
                self.url, self.text = url, urls[url]
            def raise_for_status(self):
                pass

        with tempfile.TemporaryDirectory() as tmp, patch("municipio.adapters.bergara.requests.Session.get", side_effect=lambda url, **kw: Response(url)) as get, patch("municipio.adapters.bergara.time.sleep"):
            path = Path(tmp) / "projects.jsonl"
            adapter = BergaraAyuntamientoAdapter("bergara")
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result["rows"], 1)
            self.assertEqual(len(rows[0]["documentos"]), 3)
            self.assertEqual(len(rows[0]["fuentes"]), 3)
            self.assertEqual(get.call_count, 4)
            self.assertIsNone(rows[0]["lat"])
            # A failed refresh must not replace a valid previous snapshot.
            previous = path.read_text()
            urls["https://www.bergara.eus/es/node/19972"] = "broken page"
            with self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(tmp) / "state.json")
            self.assertEqual(path.read_text(), previous)

    def test_manifest_loads_adapter_and_disables_licences(self):
        manifest = load_manifest("bergara")
        self.assertEqual(manifest.provincia, "Gipuzkoa")
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), BergaraAyuntamientoAdapter)


if __name__ == "__main__":
    unittest.main()
