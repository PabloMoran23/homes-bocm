from email.message import Message
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError

from municipio.adapters.benicarlo_vinaros_benijofar import (
    BENICARLO_RSS,
    TOWNS,
    BenicarloVinarosBenijofarAyuntamientoAdapter,
)


class CoastalTownSourceTests(TestCase):
    def setUp(self) -> None:
        self.adapter = BenicarloVinarosBenijofarAyuntamientoAdapter(
            "benicarlo-vinaros-benijofar", {"request_delay_s": 0}
        )

    def test_projects_and_licences_keep_prior_records_and_report_the_exact_gap(self) -> None:
        def read(request, **kwargs):
            if request.full_url == BENICARLO_RSS:
                self.assertEqual((kwargs["timeout"], kwargs["attempts"]), (15, 2))
                raise TimeoutError("verified provider timeout")
            return b"<rss><channel/></rss>", Message()

        seed = '<h1>Planeamiento municipal</h1><a href="/files/planeamiento.pdf">Plan</a>'
        with (
            TemporaryDirectory() as tmp,
            patch("municipio.adapters.benicarlo_vinaros_benijofar.read_response", side_effect=read),
            patch.object(self.adapter, "_fetch", return_value=seed) as fetch,
            patch.object(self.adapter, "_load_wfs_for_town", return_value=[]),
            patch.object(self.adapter, "_attach_geometry"),
        ):
            for kind in ("proyectos", "licencias"):
                with self.subTest(kind=kind):
                    path = Path(tmp) / f"{kind}.jsonl"
                    state = Path(tmp) / f"{kind}.state.json"
                    previous = {
                        "id": "benicarlo-existing", "origen": "tablon_rss", "municipio": "Benicarló",
                        "titulo": "Concesión de licencia urbanística", "tipo": "licencia urbanística",
                        "fecha_concesion": "2026-11-25", "expte": "12/2026",
                        "url": "https://example.org/document.pdf",
                    }
                    self.adapter._write_jsonl(path, [previous])

                    stats = getattr(self.adapter, f"update_{kind}")(path, state)
                    rows = self.adapter._load_jsonl(path)

                    self.assertIn(previous, rows)
                    if kind == "proyectos":
                        self.assertEqual({row["municipio"] for row in rows}, {town.municipio for town in TOWNS})
                    self.assertEqual(stats["status"], "partial")
                    self.assertEqual(stats["reason"], "benicarlo_sedipualba_edicts_unavailable")
                    self.assertEqual(stats["unavailable_sources"][0]["url"], BENICARLO_RSS)
                    self.assertIn(stats["reason"], state.read_text())

            accessed = {call.args[0] for call in fetch.call_args_list}
            self.assertTrue(all(town.board_url in accessed for town in TOWNS if town.board_url))
            self.assertTrue(all(url in accessed for town in TOWNS for url in town.seed_pages))
            self.assertFalse(any("sedipualba.es" in url for url in accessed))

    def test_mandatory_espublico_and_wfs_fail_instead_of_discarding_coverage(self) -> None:
        vinaros = TOWNS[1]
        with patch.object(self.adapter, "_fetch", side_effect=URLError("unavailable")):
            with self.assertRaises(URLError):
                self.adapter._collect_espublico_board(vinaros)
            with self.assertRaises(URLError):
                self.adapter._collect_seed_docs(vinaros)
            with self.assertRaises(URLError):
                self.adapter._load_wfs_for_town(vinaros)
        with patch(
            "municipio.adapters.benicarlo_vinaros_benijofar.read_response", side_effect=URLError("unavailable")
        ):
            with self.assertRaises(URLError):
                self.adapter._collect_tablon_rss(TOWNS[2])

    def test_rss_uses_the_xml_declared_encoding(self) -> None:
        rss = (
            '<?xml version="1.0" encoding="iso-8859-1"?>'
            "<rss><channel><item><title>Informació pública</title>"
            "<link>https://example.org/edicto</link></item></channel></rss>"
        ).encode("iso-8859-1")
        headers = Message()
        headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        with patch("municipio.adapters.benicarlo_vinaros_benijofar.read_response", return_value=(rss, headers)):
            rows, error = self.adapter._collect_tablon_rss(TOWNS[0])
        self.assertIsNone(error)
        self.assertEqual(rows[0]["titulo"], "Informació pública")
