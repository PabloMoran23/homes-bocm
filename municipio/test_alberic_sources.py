import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from municipio.adapters.alberic import AlbericAyuntamientoAdapter


class AlbericSourcesTest(TestCase):
    def setUp(self):
        self.adapter = AlbericAyuntamientoAdapter("alberic")

    def test_rss_failure_uses_official_html_listing(self):
        markup = '''<div id="site_pnlAnuncios"><table class="gridview"><tbody>
          <tr class="clickable"><td><a href="anuncio.aspx?id=123"></a></td>
          <td>25/11/2026 - 25/12/2026</td><td>Plan parcial</td></tr>
          </tbody></table></div>'''
        with patch.object(self.adapter, "_fetch_bytes", side_effect=TimeoutError("feed unavailable")), \
                patch.object(self.adapter, "_fetch", return_value=markup):
            rows, coverage = self.adapter._collect_tablon()
        self.assertEqual(coverage, {"status": "ok", "tablon_source": self.adapter.tablon_url})
        self.assertEqual(rows[0]["url"], self.adapter.tablon_url + "anuncio.aspx?id=123")
        self.assertEqual(rows[0]["fecha"], "2026-11-25")
        self.assertEqual(rows[0]["origen"], "tablon_html")

    def test_board_outage_preserves_previous_projects_and_licences(self):
        with TemporaryDirectory() as directory, \
                patch.object(self.adapter, "_fetch_bytes", side_effect=TimeoutError("feed unavailable")), \
                patch.object(self.adapter, "_fetch", side_effect=TimeoutError("board unavailable")), \
                patch.object(self.adapter, "_collect_gva_proyectos", return_value=[{"id": "icv-sector"}]), \
                patch.object(self.adapter, "_collect_web_proyectos", return_value=[]), \
                patch.object(self.adapter, "_collect_transparency_proyectos", return_value=[]):
            for label, update in (("proyectos", self.adapter.update_proyectos), ("licencias", self.adapter.update_licencias)):
                with self.subTest(label=label):
                    output, state = Path(directory) / f"{label}.jsonl", Path(directory) / f"{label}.state.json"
                    output.write_text('{"id":"prior-board-record"}\n')
                    result = update(output, state)
                    self.assertEqual(result["status"], "partial")
                    self.assertEqual(result["reason"], "alberic_sedipualba_edicts_unavailable")
                    self.assertEqual([x["url"] for x in result["unavailable_sources"]],
                                     [self.adapter.tablon_rss, self.adapter.tablon_url])
                    self.assertEqual(json.loads(state.read_text())["status"], "partial")
                    self.assertIn("prior-board-record", output.read_text())
