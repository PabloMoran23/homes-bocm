"""Offline regression tests for SIUa identity, grouping and date semantics."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sarinena import (
    SOURCE, SarinenaAyuntamientoAdapter, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def row(number, code="CPU-22/2021/191", title="MPGOU Nº 10", **fields):
    prefix = f"MPG_Exp{number}"
    cells = "".join(f'<td id="{prefix}_{key}">{value}</td>' for key, value in fields.items())
    return f'<tr><td id="{prefix}"><a href="?CODEXP={code}&FASE=4">{title}</a></td>{cells}</tr>'


def inventory(*rows):
    return "<script>cmuniineSolicitado = '22213';</script><p>MUNICIPIO SARIÑENA</p><table>" + "".join(rows) + "</table>"


def detail(code="CPU-22/2021/191", calls=""):
    return f"<script>codExpSolicitadoFicha = '{code}'; hayDatosMunicipio=true; {calls}</script>"


class SarinenaTests(unittest.TestCase):
    def test_group_history_and_distinguish_dates(self):
        html = inventory(
            row(1, FACUERDO="26/01/2022", ACUERDO="Suspender la aprobación definitiva", FPUBACUERDO="03/02/2022"),
            row(2, FACUERDO="29/06/2022", ACUERDO='Aprobar definitivamente<a href="ConsultaDocumento?CODEXP=CPU-22/2021/191">PDF</a>', FPUBACUERDO="06/07/2022"),
        )
        records = parse_inventory(html)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(len(record["tramitacion"]), 2)
        self.assertEqual(record["fecha_acuerdo"], "2022-06-29")
        self.assertEqual(record["fecha_publicacion"], "2022-07-06")
        self.assertIn("ConsultaDocumento", record["documentos"][0]["url"])
        self.assertIsNone(record["lat"])

    def test_municipal_approval_is_not_regional_report(self):
        record = parse_inventory(inventory(row(1, FACUERDO="22/08/2008", ACUERDO="Informar favorablemente con reparos", FPUBACUERDO="05/11/2008", FAPRDEF="07/11/2008", FAPRWEB="14/11/2008")))[0]
        self.assertEqual(record["fecha_aprob"], "2008-11-07")
        self.assertEqual(record["fecha_acuerdo"], "2008-08-22")
        self.assertEqual(record["fecha_publicacion"], "2008-11-05")
        self.assertEqual(record["fase"], "Informar favorablemente con reparos")

    def test_same_title_different_dossiers_and_stable_ids(self):
        a = row(1, "CPU-22/2014/153", "RECTIFICACION ERRORES PLAN GENERAL")
        b = row(2, "CPU-22/2015/48", "RECTIFICACION ERRORES PLAN GENERAL")
        records = parse_inventory(inventory(a, b))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["id"], parse_inventory(inventory(a))[0]["id"])
        self.assertIsNone(records[0]["fecha_aprob"])
        self.assertIsNone(records[0]["fecha_publicacion"])

    def test_suspension_never_becomes_approval(self):
        record = parse_inventory(inventory(row(1, FACUERDO="26/01/2022", ACUERDO="Suspender la aprobación definitiva")))[0]
        self.assertIsNone(record["fecha_aprob"])

    def test_reject_wrong_municipality_empty_navigation_and_pagination(self):
        valid = inventory(row(1))
        for html in ["<p>Solicitud licencia obras</p>", inventory(), valid.replace("'22213'", "'50213'"), valid.replace("SARIÑENA", "CARIÑENA"), valid + '<a rel="next" href="?page=2">Siguiente</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_document_grouping_and_changed_detail(self):
        call = "addDoc('NULL','0906fca30c74590c','','','','','MA12 PGOU SARIÑENA TR.pdf',codExpSolicitado,'Memoria Descriptiva');"
        docs = parse_documents(detail(calls=call + call), "CPU-22/2021/191", SOURCE)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["repository_id"], "0906fca30c74590c")
        self.assertEqual(docs[0]["url"], SOURCE)
        self.assertEqual(parse_documents(detail(), "CPU-22/2021/191", SOURCE), [])
        for html in ["<p>Login</p>", detail("CPU-22/2022/97"), detail(calls="addDoc('changed');")]:
            with self.assertRaises(ValueError):
                parse_documents(html, "CPU-22/2021/191", SOURCE)

    def test_live_failure_does_not_replace_previous_output(self):
        adapter = SarinenaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "proyectos.jsonl"
            output.write_text("previous snapshot\n")
            with patch.object(adapter, "_fetch", side_effect=[inventory(row(1)), RuntimeError("network failure")]):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), "previous snapshot\n")

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest("sarinena")
        raw = load_yaml(manifest.path)
        self.assertEqual(raw["codigo_ine"], "22213")
        self.assertEqual(manifest.provincia, "Huesca")
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw["schedule"]["enabled"])
        self.assertFalse(raw["geocode"]["jitter_missing"])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "licencias.jsonl"
            result = SarinenaAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result["rows"], 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
