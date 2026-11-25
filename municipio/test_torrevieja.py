from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from municipio.adapters.torrevieja import TorreviejaAyuntamientoAdapter


def _page(features: list[tuple[str, str]]) -> bytes:
    members = []
    for feature_id, ine in features:
        members.append(
            "<wfs:member><ms:InventarioSuSuz>"
            f"<ms:id>{feature_id}</ms:id><ms:cod_ine_mun>{ine}</ms:cod_ine_mun>"
            "</ms:InventarioSuSuz></wfs:member>"
        )
    return (
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:ms="http://mapserver.gis.umn.edu/mapserver">'
        + "".join(members)
        + "</wfs:FeatureCollection>"
    ).encode()


class TorreviejaSourceBoundaryTests(TestCase):
    def test_paginates_by_regional_count_and_publishes_only_exact_municipality(self) -> None:
        adapter = TorreviejaAyuntamientoAdapter("torrevieja")
        first = _page([(str(i), "03123") for i in range(200)])
        second = _page([("200", ""), ("201", "03123"), ("202", " 03133 ")])
        with patch.object(adapter, "_fetch_wfs", side_effect=[first, second]) as fetch:
            rows = adapter._collect_icv_wfs()

        self.assertEqual([(r["wfs_id"], r["cod_ine_mun"]) for r in rows], [("202", "03133")])
        self.assertEqual(adapter._icv_to_proyecto(rows[0])["cod_ine_mun"], "03133")
        urls = [call.args[0] for call in fetch.call_args_list]
        queries = [parse_qs(urlsplit(url).query) for url in urls]
        self.assertEqual([query["STARTINDEX"] for query in queries], [["0"], ["200"]])
        self.assertTrue(all(query["SORTBY"] == ["id"] for query in queries))

    def test_incomplete_collections_are_never_cached_as_success(self) -> None:
        adapter = TorreviejaAyuntamientoAdapter("torrevieja")
        with patch.object(adapter, "_fetch_wfs", return_value=b"<ExceptionReport/>"):
            with self.assertRaisesRegex(ValueError, "Expected a WFS FeatureCollection"):
                adapter._collect_icv_wfs()
        self.assertIsNone(adapter._wfs_cache)
