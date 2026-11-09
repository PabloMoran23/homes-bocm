"""Parser and snapshot safety tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from municipio.adapters.valga import PORTLET, SOURCE, ValgaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


TITLE = "MP nº5 do Plan xeral de ordenación municipal no núcleo rural da Gándara, Valga"
DETAIL_URL = SOURCE + "?" + urlencode({PORTLET + "id": "2886"})
INVENTORY = f'''<div id="aae"><h2>Plans en tramitación</h2><table>
<tr><th>Código</th><th>Plan ou programa</th><th>Tipoloxías</th><th>Ver proxecto</th><th>Enviar comentarios</th></tr>
<tr><td>2886/2026</td><td>{TITLE}</td><td>Outro planeamento urbanístico</td>
<td><a href="{DETAIL_URL}">Ver proxecto</a></td><td></td></tr>
<tr><td>2887/2026</td><td>Plan xeral de Portas</td><td>Outro planeamento urbanístico</td><td></td><td></td></tr>
</table></div>'''


def detail():
    fields = {
        "Nome": TITLE, "Código": "2886/2026", "Tipoloxías": "Outro planeamento urbanístico",
        "Expediente": "2026AAE3144", "Órgano promotor": "Concello de Valga",
        "Data de inicio do período de consulta": "23/10/2026",
        "Data de remate do período de consulta": "04/12/2026", "Estado:": "En curso",
    }
    html = '<div id="aae"><div class="infoContido">'
    html += ''.join(f'<p><strong>{k}</strong>{v}</p>' for k, v in fields.items())
    html += '<div class="anexos"><ul>'
    for ident, label, date in [("15383", "Documento de consultas", "23/10/2026"),
                               ("15384", "Documento ambiental estratéxico", "21/10/2026")]:
        url = SOURCE + "?" + urlencode({PORTLET + "id": "2886", PORTLET + "idCodigo": ident,
                                       PORTLET + "accion": "descarga"})
        html += f'<li><a href="{url}">{label} {date}</a></li>'
    html += '<li><a href="https://medioambiente.xunta.gal/aaedescargas/documentos_AAE/2886/288614.zip">Borrador do plan 21/10/2026</a></li>'
    return html + '</ul></div></div></div>'


class ValgaTests(unittest.TestCase):
    def setUp(self):
        self.item = Adapter.parse_inventory(INVENTORY)[0]

    def test_grouping_identity_dates_and_provenance(self):
        row = Adapter.parse_detail(detail(), self.item)
        self.assertEqual(row['id'], 'valga-proy-2026aae3144')
        self.assertEqual(row['codigo_ine'], '36056')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['fecha_inicio_consulta'], '2026-10-23')
        self.assertEqual(row['fecha_fin_consulta'], '2026-12-04')
        self.assertEqual(row['documentos'][1]['fecha_fuente'], '2026-10-21')
        self.assertEqual(row['documentos'][0]['url_ficha'], DETAIL_URL)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_inventory_filters_other_municipalities_and_deduplicates(self):
        self.assertEqual(len(Adapter.parse_inventory(INVENTORY)), 1)
        row = INVENTORY[INVENTORY.index('<tr><td>2886'):INVENTORY.index('<tr><td>2887')]
        self.assertEqual(len(Adapter.parse_inventory(INVENTORY.replace('</table>', row + '</table>'))), 1)

    def test_pagination_rejected(self):
        for paging in ('<a href="?page=2">2</a>', '<a rel="next" href="/next">→</a>',
                       '<div class="pagination">1 2</div>', '<a href="?x=2">Seguinte</a>'):
            with self.subTest(paging=paging), self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(INVENTORY.replace('</table>', '</table>' + paging))

    def test_forms_and_missing_content_rejected(self):
        for html in ('<form>Solicitude de licenza</form>', '<div id="aae"><h2>Login</h2></div>',
                     INVENTORY.replace('Valga', 'Portas')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_cross_instrument_or_external_documents_rejected(self):
        for html in (detail().replace('2026AAE3144', ''), detail().replace(TITLE, 'Plan de Portas'),
                     detail().replace('Concello de Valga', 'Concello de Portas'),
                     detail().replace('id=2886', 'id=2312'),
                     detail().replace('https://medioambiente.xunta.gal/', 'https://example.org/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_detail(html, self.item)

    def test_missing_documents_and_invalid_dates_rejected(self):
        for html in (detail().replace('class="anexos"', 'class="other"'),
                     detail().replace('23/10/2026', '32/10/2026')):
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, self.item)

    def test_failed_refresh_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch.object(Adapter, '_fetch', side_effect=ValueError('network failure')):
                with self.assertRaises(ValueError):
                    Adapter().backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')
            result = Adapter().backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest_adapter_and_guards(self):
        manifest = load_manifest('valga')
        raw = load_yaml(manifest.path)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.valga:ValgaAyuntamientoAdapter')
        self.assertEqual(raw['codigo_ine'], '36056')
        self.assertEqual(raw['provincia'], 'Pontevedra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
