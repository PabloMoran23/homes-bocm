"""Offline contract tests using minimal fixtures shaped like the verified SITEX HTML."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.miajadas import BASE, MiajadasAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


def link(key, reference, state='Vigente'):
    return (f'<a class="unenlaceafiguradeplaneamiento" '
            f'''onclick="addTab('/SITEX/ptofiguras/viewsigcat/{key}','Miajadas - {reference}');"'''
            f'><img alt="{state}">{reference}</a>')


INVENTORY_HTML = (
    '<ul id="listaplaneamientosnuevaley"><li><span>Miajadas</span><ul><li>'
    + link('37397', 'PGM') + link('40599', 'PGM.M-001')
    + '</li></ul></li></ul>'
    '<ul id="listaplaneamientosantigualey"><li><span>Miajadas</span><ul><li>'
    + link('35195', 'NNSS', 'No vigente') + '</li></ul></li></ul>'
)

DETAIL = '''
<div id="divplaneamiento37397"><div id="infoplaneamiento37397"><table>
<tr><th>Figura urbanística</th><td>Plan General Municipal</td></tr>
<tr><th>Ámbito territorial</th><td>Miajadas</td><td style="display:none">378</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Referencia</th><td>PGM</td></tr>
<tr><th>Fecha AD</th><td>21/12/2020</td></tr>
<tr><th>Fecha de depósito</th><td>22/12/2020</td></tr>
<tr><th>Fecha de publicación AD</th><td>11/02/2021</td></tr>
<tr><th>Nº de depósito</th><td>CC/054/2020</td></tr></table>
<div id="listadotramitesplaneamiento37397"><table><tr>
<td>11/02/2021</td><td><a href="http://doe.juntaex.es/pdfs/doe/2021/280o/21AC0001.pdf">Publicación en DOE de la aprobación definitiva</a></td>
</tr></table></div></div>
<div id="archivosplaneamiento37397">
<a href="/SITEX/ptofiguras/downloaddocumento/14431" download="Memoria - c121anexo.pdf"></a>
<a href="/SITEX/ptofiguras/downloaddocumento/14525" download="Memoria - c121mj.pdf"></a>
<a href="/SITEX/ptofiguras/downloaddocumento/14525" download="Memoria - c121mj.pdf"></a>
</div></div>
<footer><a href="/SITEX/files/calificacion/FormularioAutorrellenable.pdf">Solicitud licencia</a></footer>
'''


class MiajadasTests(unittest.TestCase):
    def setUp(self):
        self.entries, self.coverage = Adapter.parse_inventory(INVENTORY_HTML)

    def test_inventory_current_only_dedup_and_all_branches(self):
        self.assertEqual([e['sitex_id'] for e in self.entries], ['37397', '40599'])
        self.assertEqual(self.coverage, {'inventory_records': 3, 'excluded_not_current': 1})
        html = INVENTORY_HTML.replace(link('37397', 'PGM'), link('37397', 'PGM') * 2)
        self.assertEqual(Adapter.parse_inventory(html), (self.entries, self.coverage))

    def test_dates_documents_and_identity(self):
        row = Adapter.parse_instrument(DETAIL, self.entries[0])
        self.assertEqual(row['codigo_ine'], '10121')
        self.assertEqual(row['fecha_aprob'], '2020-12-21')
        self.assertEqual(row['fecha_publicacion'], '2021-02-11')
        self.assertEqual(row['fecha_deposito'], '2020-12-22')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['fase'], 'Vigente')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['url'], BASE + '/SITEX/ptofiguras/downloaddocumento/14431')
        self.assertEqual(row['tramites'][0]['fecha_tramite'], '2021-02-11')
        self.assertFalse(row['publication_ready'])

    def test_missing_dates_never_filled_from_other_dates(self):
        html = DETAIL.replace('21/12/2020', '').replace('11/02/2021', '')
        row = Adapter.parse_instrument(html, self.entries[0])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['fecha_deposito'], '2020-12-22')
        with self.assertRaises(ValueError):
            Adapter.parse_instrument(DETAIL.replace('21/12/2020', '31/02/2020'), self.entries[0])

    def test_inventory_fails_on_scope_change_empty_or_pagination(self):
        for html in [
            '<h1>Login</h1>', INVENTORY_HTML.replace('Miajadas', 'Majadas'),
            INVENTORY_HTML.replace('Vigente', 'Desconocido'),
            INVENTORY_HTML.replace('Vigente', 'No vigente'),
            INVENTORY_HTML + '<a rel="next" href="?page=2">2</a>',
            INVENTORY_HTML + '<div class="paging">1 2</div>',
        ]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_detail_fails_on_scope_identity_and_documents(self):
        for html in [
            '<a href="formulario.pdf">Solicitud de licencia</a>',
            DETAIL.replace('Miajadas', 'Majadas'), DETAIL.replace('Vigente', 'No vigente'),
            DETAIL.replace('<td>PGM</td>', '<td>NNSS</td>'),
            DETAIL.replace('href=', 'data-removed-href='),
            DETAIL.replace('</table>', '</table><a href="?page=2">Siguiente</a>', 1),
        ]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_instrument(html, self.entries[0])

    def test_refresh_and_disabled_licences(self):
        adapter = Adapter('miajadas')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('projects'), Path('state')), {'rows': 2})
            backfill.assert_called_once_with(Path('projects'))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            adapter._write(path, [Adapter.parse_instrument(DETAIL, self.entries[0])])
            self.assertEqual(json.loads(path.read_text())['id'], 'miajadas-sitex-37397')

    def test_manifest(self):
        manifest = load_manifest('miajadas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia), ('Miajadas', 'Cáceres'))
        self.assertEqual(raw['codigo_ine'], '10121')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.miajadas:MiajadasAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
