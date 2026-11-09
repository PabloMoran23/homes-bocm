"""Parser regressions; synthetic markup mirrors the public register structure."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from municipio.adapters.guenes import (
    GuenesAyuntamientoAdapter, discover_inventory, parse_detail, parse_inventory,
)

DETAIL_URL = ('https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador?'
              '_test_idInstrumento=123&_test_idMunicipio=45')
ENTRY = {'registry_id': '123', 'url': DETAIL_URL, 'expected_documents': 2}
DETAIL = '''<div class="planeamiento-urbanistico-detalle">
<h1>PLAN ESPECIAL ARANGOITI</h1>
<p role="heading">Expediente</p><p>B-HI-136/2016-P08-N</p>
<p role="heading">Municipio/s</p><p>Gueñes</p>
<div class="cajaListado"><ul>
<li><span class="negrita">Estado:</span> Vigente</li>
<li><span class="negrita">Figura de planeamiento:</span> Plan especial o su modificación</li>
</ul></div>
<div class="cajaAprobacion"><h3>Aprobación definitiva</h3><ul>
<li><span class="negrita">Fecha de Resolución</span><span class="textoGrande">30/05/2016</span></li>
<li><span class="negrita">Fecha de publicación resolución en BOB</span><span class="textoGrande">15/06/2016</span>
<a href="https://www.bizkaia.eus/boletin.pdf ">Ir a la publicación</a></li>
</ul></div>
<ul id="bipo_acordeon_feature_docs">
<li><a class="UIB_btn-descarga" href="https://www.bizkaia.eus/o/repo/document?id=memoria;2.0 ">Memoria PDF</a></li>
<li><a class="UIB_btn-descarga" href="https://www.bizkaia.eus/o/repo/document?id=plano;2.0">Plano PDF</a></li>
</ul></div>'''


def inventory(total=1, duplicate=False, municipality='45'):
    link = DETAIL_URL.replace('Municipio=45', 'Municipio=' + municipality)
    anchor = f'<a href="{link}">2 Documentos</a>'
    return f'<div class="planeamiento-urbanistico">{total} resultados de búsqueda de {anchor}{anchor if duplicate else ""}</div>'


class GuenesParserTests(unittest.TestCase):
    def test_discover_query_from_form(self):
        html = '''<form data-fm-namespace="_new_" action="/es/planeamiento-urbanistico-buscador?p_p_id=new">
        <select name="_new_select-municipios"><option value="45">GUEÑES</option></select></form>'''
        query = parse_qs(urlsplit(discover_inventory(html)).query)
        self.assertEqual(query['_new_select-municipios'], ['45'])
        self.assertEqual(query['_new_select-figuras'], ['-1'])
        with self.assertRaises(ValueError):
            discover_inventory(html.replace('GUEÑES', 'OTRO'))

    def test_inventory_identity_and_completeness(self):
        rows = parse_inventory(inventory(duplicate=True))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['registry_id'], '123')
        for html in [inventory(total=2), inventory(municipality='44'), '<html>error</html>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_one_instrument_retains_documents_and_date_semantics(self):
        row = parse_detail(DETAIL, ENTRY, 'https://www.bizkaia.eus/inventory')
        self.assertEqual(row['fecha_acuerdo'], '2016-05-30')
        self.assertEqual(row['fecha_publicacion'], '2016-06-15')
        self.assertEqual(row['fase'], 'Aprobación definitiva')
        self.assertEqual(row['codigo_ine'], '48045')
        self.assertEqual(row['documentos_instrumento_count'], 2)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][0]['url'], 'https://www.bizkaia.eus/o/repo/document?id=memoria;2.0')
        self.assertNotIn('lat', row)
        self.assertNotIn('fecha', row)
        self.assertNotIn('fecha_aprob', row)

    def test_missing_or_foreign_documents_and_wrong_municipality_fail(self):
        for html in [DETAIL.replace('Gueñes', 'Bilbao'),
                     DETAIL.replace('UIB_btn-descarga', 'removed', 1),
                     DETAIL.replace('https://www.bizkaia.eus/o/repo/document?id=memoria', 'https://example.org/doc')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, ENTRY, 'inventory')

    def test_absent_dates_not_invented_and_licences_disabled(self):
        row = parse_detail(DETAIL.replace('30/05/2016', '').replace('15/06/2016', ''), ENTRY, 'inventory')
        self.assertNotIn('fecha_acuerdo', row)
        self.assertNotIn('fecha_publicacion', row)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = GuenesAyuntamientoAdapter('guenes').backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
