from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from municipio.anuncio_clase import clasificar
from municipio.gestiona_board import BoardResult, board_url_for, parse_rows, read_board
from municipio.manifest import load_manifest
from municipio.orchestrator import _steps_for

BOARD = "https://conil.sedelectronica.es/board/"


def _row(doc: str, titulo: str, *, exp="1/2026", proc="Procedimiento Genérico", cat="Anuncios",
         desc="", fecha="24/11/2026") -> str:
    return f"""<tr class="even">
      <td class="class_name" data-label="Documento"><span><a onclick="var wcall=wicketAjaxGet('../?x=abc');"
        href="https://conil.sedelectronica.es/preview-document/{doc}" title="{titulo}">{titulo}</a></span></td>
      <td class="class_folderCode" data-label="Expediente"><span>{exp}</span></td>
      <td class="class_folderName" data-label="Procedimiento"><span>{proc}</span></td>
      <td class="class_boardCategory" data-label="Categoría"><span>{cat}</span></td>
      <td class="class_description" data-label="Descripción"><span>{desc}</span></td>
      <td class="class_dateFrom" data-label="Fecha de Publicación"><span><span>{fecha}</span></span></td>
    </tr>"""


def _page(rows: list[str], more: str | None) -> str:
    button = (
        f"""<div class="more_results" id="id1c"><span><button id="id1d" onclick="var wcall=wicketAjaxGet('{more}',null,null,
        function() {{return Wicket.$('id1d') != null;}}.bind(this));return !wcall;">Mostrar más</button></span></div>"""
        if more else ""
    )
    return f"<html><body><table><tbody>{''.join(rows)}</tbody></table>{button}</body></html>"


def _doc(n: int) -> str:
    return f"00000000-0000-0000-0000-{n:012d}"


class GestionaBoardTest(TestCase):
    def test_parse_rows_extracts_fields_and_stable_id(self) -> None:
        html = _page([_row(_doc(1), "Anuncio &amp; edicto", exp="10655/2026", proc="Licencias de Ocupación",
                           cat="Bandos", desc="Bando <b>fiestas</b>", fecha="20/10/2026")], None)
        [row] = parse_rows(html, BOARD)
        self.assertEqual(row["titulo"], "Anuncio & edicto")
        self.assertEqual((row["expediente"], row["procedimiento"], row["categoria"]),
                         ("10655/2026", "Licencias de Ocupación", "Bandos"))
        self.assertEqual(row["descripcion"], "Bando fiestas")
        self.assertEqual(row["fecha_publicacion"], "2026-10-20")
        self.assertEqual(row["documento_id"], _doc(1))
        self.assertEqual(row["url"], f"https://conil.sedelectronica.es/preview-document/{_doc(1)}")
        self.assertEqual(row["sede"], "conil.sedelectronica.es")
        self.assertEqual(parse_rows(html, BOARD)[0]["id"], row["id"])

    def test_read_board_clicks_more_until_no_new_rows(self) -> None:
        pages = [
            _page([_row(_doc(i), f"A{i}") for i in range(10)], "../?x=one"),
            # Wicket puede reenviar filas ya vistas: no se duplican.
            _page([_row(_doc(i), f"A{i}") for i in range(5, 20)], "../?x=two"),
            _page([_row(_doc(i), f"A{i}") for i in range(20, 23)], None),
        ]
        requests = []

        def fetch(request):
            requests.append(request)
            return pages[len(requests) - 1]

        result = read_board(BOARD, fetch=fetch, sleep=lambda _: None)
        self.assertEqual(len(result.anuncios), 23)
        self.assertEqual((result.clicks, result.truncated), (2, False))
        self.assertEqual(requests[1].full_url, "https://conil.sedelectronica.es/?x=one")
        self.assertEqual(requests[1].get_header("Wicket-ajax"), "true")

    def test_read_board_stops_at_max_clicks_and_reports_truncation(self) -> None:
        counter = iter(range(1000))

        def fetch(request):
            n = next(counter)
            return _page([_row(_doc(n * 10 + i), f"A{n}-{i}") for i in range(10)], f"../?x={n}")

        result = read_board(BOARD, fetch=fetch, sleep=lambda _: None, max_clicks=3)
        self.assertEqual((len(result.anuncios), result.clicks, result.truncated), (40, 3, True))

    def test_read_board_rejects_non_board_page(self) -> None:
        with self.assertRaises(RuntimeError):
            read_board(BOARD, fetch=lambda request: "<html>Error</html>", sleep=lambda _: None)

    def test_board_url_from_manifest(self) -> None:
        self.assertEqual(
            board_url_for({"portal": {"config": {"board_url": "https://Ador.sedelectronica.es/board"}}}),
            "https://ador.sedelectronica.es/board/",
        )
        self.assertEqual(
            board_url_for({"portal": {"base_url": "https://www.x.es", "notes": "sede https://x.sedelectronica.es/info"}}),
            "https://x.sedelectronica.es/board/",
        )
        self.assertIsNone(board_url_for({"portal": {"base_url": "https://www.manlleu.cat"}}))
        self.assertIsNone(board_url_for({"portal": {"base_url": "https://x.sedelectronica.es"}, "anuncios": {"enabled": False}}))


class AnuncioClaseTest(TestCase):
    def check(self, expected: str, **anuncio) -> None:
        self.assertEqual(clasificar(anuncio)["clase"], expected, anuncio)

    def test_catalog_and_text_rules(self) -> None:
        self.check("empleo_publico", titulo="PROPUESTA DE CONTRATACION OFICIAL PRIMERA",
                   procedimiento="Selecciones de Personal y Provisiones de Puestos")
        self.check("planeamiento", titulo="ESTUDIO DE DETALLE TC", procedimiento="Licencias Urbanísticas")
        self.check("enajenacion_patrimonio", titulo="ANUNCIO PINOS SECOS", procedimiento="Contrataciones Patrimoniales")
        self.check("contratacion_licitacion", titulo="Anuncio_licitación_DOC", procedimiento="Contrataciones")
        self.check("vivienda_protegida", titulo="Acta sorteo 18 viviendas protegidas alquiler joven",
                   procedimiento="Certificados o Informes")
        self.check("ambiental", titulo="19828-26 EDICTO NUEVO", procedimiento="Calidad Ambiental")
        self.check("energia", titulo="Información pública instalación fotovoltaica en polígono 3")

    def test_ocupacion_de_via_publica_is_not_primera_ocupacion(self) -> None:
        self.check("bando_aviso", titulo="Bando Zambombas Navideñas", procedimiento="Licencias de Ocupación",
                   categoria="Bandos")
        result = clasificar({"titulo": "Licencia de primera ocupación C/ Mayor 3"})
        self.assertEqual((result["clase"], result["subclase"]), ("licencia_obra", "primera_ocupacion"))

    def test_generic_classes_only_as_fallback(self) -> None:
        self.check("organos_gobierno", titulo="Decreto de la convocatoria", procedimiento="Convocatoria de El Pleno")
        self.check("otros", titulo="ANUNCIO EXPEDICIÓN DEL DNI", procedimiento="Procedimiento Genérico")


class AnunciosRunnerTest(TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest = load_manifest("conil-de-la-frontera")
        self.manifest._output_dir = Path(self.tmp.name)

    def test_writes_classified_rows_and_state(self) -> None:
        from municipio import anuncios_runner

        anuncios = parse_rows(_page([_row(_doc(1), "Anuncio licitación obras", proc="Contrataciones")], None), BOARD)
        fake = lambda url, **kw: BoardResult(board_url=url, anuncios=anuncios, clicks=0, truncated=False)
        result = anuncios_runner.update(self.manifest, read=fake)
        self.assertEqual((result["status"], result["rows"]), ("ok", 1))
        [row] = [json.loads(l) for l in (Path(self.tmp.name) / "anuncios.jsonl").read_text().splitlines()]
        self.assertEqual((row["clase"], row["municipio_slug"]), ("contratacion_licitacion", "conil-de-la-frontera"))
        state = json.loads((Path(self.tmp.name) / "anuncios_state.json").read_text())
        self.assertTrue(state["complete"])

    def test_failure_is_not_fatal_and_clears_previous_capture(self) -> None:
        from municipio import anuncios_runner

        (Path(self.tmp.name) / "anuncios.jsonl").write_text('{"id": "viejo"}\n')
        def boom(url, **kw):
            raise TimeoutError("timeout")
        result = anuncios_runner.update(self.manifest, read=boom)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("error", result)
        self.assertFalse((Path(self.tmp.name) / "anuncios.jsonl").exists())

    def test_skipped_without_gestiona(self) -> None:
        from municipio import anuncios_runner

        manifest = load_manifest("manlleu")
        manifest._output_dir = Path(self.tmp.name)
        self.assertEqual(anuncios_runner.update(manifest)["status"], "skipped")

    def test_update_and_backfill_include_anuncios_before_sync(self) -> None:
        for step in ("update", "backfill", "all"):
            steps = _steps_for(step)
            self.assertLess(steps.index("anuncios_update"), steps.index("sync_supabase"), step)


class SyncAnunciosTest(TestCase):
    def test_sync_failure_does_not_fail_main_ingest(self) -> None:
        from municipio import sync_supabase

        manifest = load_manifest("conil-de-la-frontera")
        with patch.dict("os.environ", {"SUPABASE_DB_URL": "postgres://x"}), patch(
            "municipio.sync_supabase.sync_municipio_output", return_value={"status": "ok"}
        ), patch("anuncios.sync_municipio_anuncios", side_effect=RuntimeError("tabla bloqueada")):
            result = sync_supabase.sync_manifest(manifest)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["anuncios"]["status"], "failed")
