import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError

from municipio.adapters.ontinyent import CATALOGO_TRAMITES, TABLON_HTML, TABLON_RSS, OntinyentAyuntamientoAdapter


class OntinyentSourcesTest(TestCase):
    def setUp(self):
        self.adapter = OntinyentAyuntamientoAdapter("ontinyent")

    def test_rss_timeout_uses_official_html_announcement(self):
        markup = '''<div id="site_pnlAnuncios"><table class="gridview"><tbody>
          <tr class="clickable"><td><a href="anuncio.aspx?id=123"></a></td>
          <td>25/11/2026 - 25/12/2026</td><td>Aprovació del Pla parcial</td></tr>
          </tbody></table></div>'''
        with patch.object(self.adapter, "_collect_tablon_rss", side_effect=TimeoutError("RSS unavailable")), \
                patch.object(self.adapter, "_fetch", return_value=markup):
            rows, coverage = self.adapter._collect_tablon()
        self.assertEqual(coverage, {"status": "ok", "tablon_source": TABLON_HTML})
        self.assertEqual(rows[0]["url"], f"{TABLON_HTML}anuncio.aspx?id=123")
        self.assertEqual(rows[0]["fecha"], "2026-11-25")

    def test_planning_and_licence_updates_preserve_history_during_board_outage(self):
        feature = {"titulo": "Sector actual", "url": "https://example.org/icv", "wfs_id": "sector"}
        with TemporaryDirectory() as temp, \
                patch.object(self.adapter, "_collect_tablon_rss", side_effect=TimeoutError("RSS unavailable")), \
                patch.object(self.adapter, "_collect_tablon_html", side_effect=TimeoutError("HTML unavailable")), \
                patch.object(self.adapter, "_collect_tramites", side_effect=TimeoutError("catalogue unavailable")), \
                patch.object(self.adapter, "_collect_icv_wfs", return_value=[feature]), \
                patch.object(self.adapter, "_crawl_drupal_pages", return_value=[]):
            for label, update, urls in (
                ("projects", self.adapter.update_proyectos, [TABLON_RSS, TABLON_HTML]),
                ("licences", self.adapter.update_licencias, [TABLON_RSS, TABLON_HTML, CATALOGO_TRAMITES]),
            ):
                with self.subTest(label=label):
                    output, state = Path(temp) / f"{label}.jsonl", Path(temp) / f"{label}.state.json"
                    output.write_text('{"id":"history"}\n')
                    result = update(output, state)
                    self.assertEqual(result["status"], "partial")
                    self.assertEqual([item["url"] for item in result["unavailable_sources"]], urls)
                    self.assertIn('"id": "history"', output.read_text())
                    self.assertEqual(json.loads(state.read_text())["status"], "partial")

    def test_catalogue_failure_reports_partial_and_retains_board_notices(self):
        notice = {"titulo": "Llicència d'obres", "url": TABLON_HTML + "anuncio.aspx?id=123", "origen": "tablon_rss"}
        with patch.object(self.adapter, "_collect_tablon_rss", return_value=[notice]), \
                patch.object(self.adapter, "_collect_tramites", side_effect=URLError("catalogue unavailable")), \
                patch.object(self.adapter, "_attach_geometry"):
            rows, coverage = self.adapter._collect_licencias()
        self.assertEqual(coverage["status"], "partial")
        self.assertEqual(coverage["reason"], "ontinyent_sedipualba_catalogue_unavailable")
        self.assertEqual(coverage["unavailable_sources"][0]["url"], CATALOGO_TRAMITES)
        self.assertEqual([row["url"] for row in rows], [notice["url"]])
