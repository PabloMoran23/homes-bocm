"""Offline parser and adapter contract checks; no network in unit tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arroyo_de_san_servan import (
    ArroyoDeSanServanAyuntamientoAdapter, MUNICIPIO, parse_inventory, parse_instrument,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def entry(ident='42', name=MUNICIPIO + ' - PGM', status='Vigente'):
    return f'''<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/{ident}','{name}');"><img alt="{status}">PGM</a>'''


def inventory(content):
    return f'<select id="PtofiguraMunicipio"><option selected value="13">{MUNICIPIO}</option></select>{content}'


DETAIL = f'''<div id="cabeceraplaneamiento42"><h1>Plan General Municipal<br>{MUNICIPIO}</h1></div>
<div id="infoplaneamiento42"><table>
<tr><th>Figura urbanística</th><td>Plan General Municipal</td></tr>
<tr><th>Ámbito territorial</th><td>{MUNICIPIO}</td><td>13</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr><tr><th>Referencia</th><td>PGM</td></tr>
<tr><th>Fecha AD</th><td>13/07/2017</td></tr>
<tr><th>Fecha de publicación AD</th><td>14/12/2017</td></tr>
<tr id="filatramite1"><td>12/01/2018</td><td>Publicación en Sede</td></tr>
<tr><td><a href="http://doe.juntaex.es/pdfs/official.pdf">Publicación DOE</a></td></tr>
</table></div><div id="archivosplaneamiento42">
<a href="/SITEX/ptofiguras/downloaddocumento/7" download="Memoria.pdf"></a>
<a href="/SITEX/ptofiguras/downloaddocumento/7" download="Memoria.pdf"></a></div>'''
URL = 'https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/42'


class ParserTests(unittest.TestCase):
    def test_discovery_scope_and_deduplication(self):
        rows = parse_inventory(inventory(entry() + entry() + entry('43', status='No vigente') + entry('44', name='Plan Territorial de Mérida')))
        self.assertEqual(rows, {'42': URL})

    def test_identity_and_empty_fail_closed(self):
        for html in ('<html>Login</html>', inventory(entry(status='No vigente')), inventory(entry()).replace('value="13"', 'value="14"')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected(self):
        for marker in ('<a rel="next" href="?page=2">2</a>', '<div class="paging">2</div>', '<a href="?page=2">Siguiente</a>'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                parse_inventory(inventory(entry()) + marker)

    def test_dates_and_document_grouping(self):
        row = parse_instrument(DETAIL, '42', URL)
        self.assertEqual(row['fecha_aprob'], '2017-07-13')
        self.assertEqual(row['fecha_publicacion'], '2017-12-14')
        self.assertEqual(row['tramites'][0]['fecha'], '2018-01-12')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['url'], 'https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/7')

    def test_invalid_detail_rejected(self):
        for html in ('<html/>', DETAIL.replace(MUNICIPIO, 'Otro municipio'), DETAIL.replace('Vigente', 'No vigente'), DETAIL.replace('13/07/2017', '32/07/2017')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_instrument(html, '42', URL)

    def test_refresh_failure_preserves_previous_output(self):
        adapter = ArroyoDeSanServanAyuntamientoAdapter('arroyo-de-san-servan')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(entry()), '<html/>']):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), 'previous snapshot\n')
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('arroyo-de-san-servan')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '06012')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), ArroyoDeSanServanAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
