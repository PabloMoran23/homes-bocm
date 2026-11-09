import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.valencia_de_alcantara import ValenciaDeAlcantaraAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


INVENTORY = '''<select id="PtofiguraMunicipio"><option value="491" selected>Valencia de Alcántara</option></select>
<div id="capaderesultadosportramosdeley">
<a class="unenlaceafiguradeplaneamiento" title="REVISIÓN NORMAS SUBSIDIARIAS"
 onclick="addTab('/SITEX/ptofiguras/viewsigcat/34967','NNSS');"><img alt="Vigente"></a>
<a class="unenlaceafiguradeplaneamiento" title="Plan General Municipal"
 onclick="addTab('/SITEX/ptofiguras/viewsigcat/37157','PGM');"><img alt="En trámite"></a>
<a class="unenlaceafiguradeplaneamiento" title="Plan Territorial Sierra de San Pedro"
 onclick="addTab('/SITEX/ptofiguras/viewsigcat/39857','PT');"><img alt="Vigente"></a>
<a class="unenlaceafiguradeplaneamiento" title="Modificación no vigente"><img alt="No vigente"></a></div>'''


def detail(ident='34967', title='REVISIÓN NORMAS SUBSIDIARIAS', doc='1460'):
    return f'''<div id="infoplaneamiento{ident}"><table>
<tr><th>Figura urbanística</th><td>{title}</td></tr>
<tr><th>Ámbito territorial</th><td>Valencia de Alcántara</td><td hidden>491</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr><tr><th>Referencia</th><td>NNSS.R-001</td></tr>
<tr><th>Fecha AD</th><td>29/10/1998</td></tr>
<tr><th>Fecha de publicación AD</th><td>16/03/1999</td></tr>
<tr id="filatramite1"><td>16/03/1999</td><td><a href="https://doe.juntaex.es/issue">Publicación en DOE de la aprobación definitiva</a></td></tr>
</table></div><div id="archivosplaneamiento{ident}">
<a href="/SITEX/ptofiguras/downloaddocumento/{doc}" download="Memoria.pdf">PDF</a>
<a href="/SITEX/ptofiguras/downloaddocumento/{doc}" download="Memoria.pdf">PDF</a>
<a href="/SITEX/ptofiguras/downloaddocumento/{int(doc)+1}" download="Planos.pdf">PDF</a></div>
<nav><a href="/formulario.pdf">Solicitud licencia</a></nav>'''


class ParserTests(unittest.TestCase):
    def test_inventory_scope_and_identity(self):
        items = Adapter.parse_inventory(INVENTORY)
        self.assertEqual([r['sitex_id'] for r in items], ['34967'])
        for html in ['', INVENTORY.replace('Valencia de Alcántara', 'Alcántara'),
                     INVENTORY.replace('Vigente', 'Desconocido')]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_no_silent_pagination(self):
        for nav in ['<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Siguiente</a>',
                    '<div class="paging">1 2</div>']:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(INVENTORY + nav)

    def test_dates_and_grouping(self):
        item = Adapter.parse_inventory(INVENTORY)[0]
        row = Adapter.parse_detail(detail(), item)
        self.assertEqual(row['fecha_aprob'], '1998-10-29')
        self.assertEqual(row['fecha_publicacion'], '1999-03-16')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(len([d for d in row['documentos'] if d['tipo'] == 'documento_tecnico']), 2)
        self.assertFalse(any('formulario' in d['url'] for d in row['documentos']))
        self.assertEqual(row['tramites'][0]['fecha'], '1999-03-16')
        other = Adapter.parse_detail(detail('32111', 'Estudio de Detalle de la UE-23', '2000'),
                                     {'sitex_id': '32111', 'url': item['url'].replace('34967', '32111')})
        self.assertNotEqual(row['id'], other['id'])
        self.assertFalse(any('/1460' in d['url'] for d in other['documentos']))

    def test_missing_dates_and_documents(self):
        item = Adapter.parse_inventory(INVENTORY)[0]
        html = detail().replace('29/10/1998', '').replace('16/03/1999', '')
        # A blank date in a dated procedure row is preserved as unknown.
        row = Adapter.parse_detail(html, item)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        html = detail().split('<div id="archivosplaneamiento')[0]
        row = Adapter.parse_detail(html, item)
        self.assertEqual([d['tipo'] for d in row['documentos']], ['publicacion_tramite'])

    def test_reject_wrong_or_changed_details(self):
        item = Adapter.parse_inventory(INVENTORY)[0]
        for html in ['', detail().replace('Valencia de Alcántara', 'Alcántara'),
                     detail().replace('Vigente', 'No vigente'), detail().replace('29/10/1998', '31/02/1998'),
                     detail().replace('downloaddocumento/', 'unknown/')]:
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, item)

    def test_manifest_and_atomic_live_path(self):
        manifest = load_manifest('valencia-de-alcantara')
        self.assertEqual(manifest.provincia, 'Cáceres')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        class Response:
            def __init__(self, text): self.text = text
            def raise_for_status(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.request',
                side_effect=[Response(INVENTORY), Response(detail())]) as request:
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '10203')
            self.assertEqual(request.call_args_list[0].kwargs['data'], {'municipioseleccionado': '491'})
            previous = out.read_text()
            with patch('requests.Session.request', side_effect=[Response(INVENTORY), Response('broken')]):
                with self.assertRaises(ValueError): adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), previous)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['rows'], 0)


if __name__ == '__main__':
    unittest.main()
