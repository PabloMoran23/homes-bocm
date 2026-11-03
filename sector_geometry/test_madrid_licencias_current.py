import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from sector_geometry.madrid_licencias_current import parse_csv, refresh
from sector_geometry.madrid_licencias_download import licencia_key


def resource(kind="licencias", **changes):
    row = {"Nº_EXPEDIENTE": "350/2026/00001", "TIPO": "Licencia urbanística residencial",
           "NDP": "110001", "FECHA_ALTA": "martes, 3 de marzo de 2026",
           "DIRECCION": "MAYOR", "VIA": "CL", "Nº": "3"}
    prefixes = ("FECHA_ALTA", "FECHA_FIRMA_RESOLUCION") if kind == "licencias" else ("FECHA_ALTA_EXPEDIENTE",)
    for prefix in prefixes:
        row.update({f"{prefix} - Año": "2026", f"{prefix} - Mes": "marzo", f"{prefix} - Día": "3"})
    if kind == "licencias":
        row["RESOLUCION"] = "Conceder"
    else:
        row["TIPO"] = "Declaración Responsable - Actividad"
    row.update(changes)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(row), delimiter=";")
    writer.writeheader()
    writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")


class CurrentSourcesTest(unittest.TestCase):
    def test_grant_and_registration_are_distinct(self):
        origin = {"dataset": "640505"}
        row = parse_csv(resource(), "licencias", origin=origin, locations={})[0]
        self.assertEqual(row["fecha_concesin"], "2026-03-03")
        dr = parse_csv(resource("declaraciones"), "declaraciones", origin=origin, locations={})[0]
        self.assertIsNone(dr["fecha_concesin"])
        self.assertEqual(dr["fecha_de_alta"], "2026-03-03")
        self.assertEqual(dr["_source_record"]["TIPO"], "Declaración Responsable - Actividad")

    def test_coordinates_only_reused_for_same_ndp(self):
        old = {"coordenadas_x": "44000000", "coordenadas_y": "447000000"}
        row = parse_csv(resource(), "licencias", origin={"dataset": "source"}, locations={"110001": old})[0]
        self.assertEqual(row["coordenadas_x"], old["coordenadas_x"])
        other = parse_csv(resource(), "licencias", origin={"dataset": "source"}, locations={"other": old})[0]
        self.assertNotIn("coordenadas_x", other)

    def test_key_survives_corrected_grant_date(self):
        row = {"source_dataset": "640505", "numero_expediente": "350/2026/1", "ndp_edificio": "123"}
        self.assertEqual(licencia_key(row, anio=2025), licencia_key({**row, "fecha_concesin": "2026-01-01"}, anio=2026))
        self.assertNotEqual(licencia_key(row, anio=2026), licencia_key({**row, "ndp_edificio": "456"}, anio=2026))

    def test_bad_schema_or_date_fails(self):
        with self.assertRaises(ValueError):
            parse_csv(b"html error", "licencias", origin={}, locations={})
        with self.assertRaises(ValueError):
            parse_csv(resource(**{"FECHA_ALTA - Día": "32"}), "licencias", origin={}, locations={})

    def test_snapshot_replaces_recent_legacy_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out, summary = root / "licenses.jsonl", root / "summary.json"
            out.write_text(json.dumps({"anio_dataset": 2022, "ndp_edificio": "old"}) + "\n" + json.dumps({"anio_dataset": 2026, "ndp_edificio": "replaced"}) + "\n")
            def fetch(req, **kwargs):
                kind = "licencias" if "640505" in req.full_url else "declaraciones"
                return io.BytesIO(resource(kind))
            with patch("urllib.request.urlopen", side_effect=fetch):
                for _ in range(2):
                    result = refresh(root, root / "raw", out, summary)
                    self.assertEqual(result["totalRows"], 3)
            self.assertNotIn("replaced", out.read_text())
            before = out.read_bytes(), summary.read_bytes()
            def partial_failure(req, **kwargs):
                if "133556" in req.full_url:
                    raise HTTPError(req.full_url, 403, "Forbidden", {}, None)
                return io.BytesIO(resource())
            with patch("urllib.request.urlopen", side_effect=partial_failure):
                with self.assertRaises(HTTPError):
                    refresh(root, root / "raw", out, summary)
            self.assertEqual(before, (out.read_bytes(), summary.read_bytes()))
