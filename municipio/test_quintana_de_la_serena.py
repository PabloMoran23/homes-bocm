"""Offline parser/adapter regression tests; fixtures reproduce the SITEX structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.quintana_de_la_serena import (
    QuintanaDeLaSerenaAyuntamientoAdapter, parse_inventory, parse_detail,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def link(number, ref, state='Vigente'):
    return f'''<a class="unenlaceafiguradeplaneamiento"
    onclick="addTab('/SITEX/ptofiguras/viewsigcat/{number}','Quintana de la Serena - {ref}');">
    <img alt="{state}">{ref}</a>'''


INVENTORY = '''<select id="PtofiguraMunicipio"><option selected value=""></option>
<option selected value="154">Quintana de la Serena</option></select>''' + (
    link('37335', 'PGM') + link('37404', 'PGM.M-003') + link('37404', 'PGM.M-003')
    + link('39696', 'PGM.M-004', 'En trámite') + link('32843', 'NNSS.R-001.ED-001', 'No vigente')
    + link('40522', 'PT-003.M-001', 'En trámite')
)


def detail(number='37404', ref='PGM.M-003', state='Vigente', dates=True):
    return f'''<div id="infoplaneamiento{number}"><table>
<tr><th>Figura urbanística</th><td>Modificación puntual nº 3/2013 del Plan General Municipal, Sector SUB-09</td></tr>
<tr><th>Ámbito territorial</th><td>Quintana de la Serena</td><td style="display:none">154</td></tr>
<tr><th>Estado</th><td>{state}</td></tr><tr><th>Referencia</th><td>{ref}</td></tr>''' + (
        '''<tr><th>Fecha AD</th><td>26/06/2014</td></tr>
<tr><th>Fecha de publicación AD</th><td>15/10/2014</td></tr>''' if dates else ''
    ) + f'''<tr><td>22/10/2013</td><td><a href="http://doe.juntaex.es/notice.pdf">Información pública inicial en DOE</a></td></tr>
</table></div><div id="archivosplaneamiento{number}">
<a download="Memoria justificativa - b109j.pdf" href="/SITEX/ptofiguras/downloaddocumento/{number}">PDF</a>
<a download="Memoria justificativa - b109j.pdf" href="/SITEX/ptofiguras/downloaddocumento/{number}">PDF</a>
</div>'''


class ParserTests(unittest.TestCase):
    def test_inventory_scoping_and_deduplication(self):
        self.assertEqual(parse_inventory(INVENTORY), ['37335', '37404', '39696'])

    def test_fail_closed_on_empty_wrong_municipality_and_pagination(self):
        for html in ('<html>Forbidden</html>', INVENTORY.replace('value="154"', 'value="155"'),
                     INVENTORY + '<a rel="next" href="?page=2">2</a>',
                     INVENTORY + '<div class="paging">2</div>',
                     INVENTORY.replace('alt="Vigente"', 'alt="Desconocido"')):
            with self.subTest(html=html[-80:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_specific_title_dates_and_documents(self):
        r = parse_detail(detail(), '37404')
        self.assertIn('Sector SUB-09', r['titulo'])
        self.assertEqual(r['fecha_aprob'], '2014-06-26')
        self.assertEqual(r['fecha_publicacion'], '2014-10-15')
        self.assertNotIn('fecha_acuerdo', r)
        self.assertNotIn('lat', r)
        self.assertNotIn('fecha', r)
        self.assertEqual(len(r['documentos']), 2)
        self.assertEqual(r['documentos'][1]['titulo'], 'Memoria justificativa - b109j.pdf')
        self.assertTrue(r['documentos'][1]['url'].startswith('https://sitex.juntaex.es/'))
        self.assertTrue(all(d['source_url'] == r['url'] for d in r['documentos']))

    def test_missing_dates_not_inferred_from_initial_publication(self):
        r = parse_detail(detail(state='En trámite', dates=False), '37404')
        self.assertNotIn('fecha_aprob', r)
        self.assertNotIn('fecha_publicacion', r)
        self.assertEqual(r['estado_fuente'], 'En trámite')

    def test_reject_wrong_detail_or_inactive(self):
        for html, number in [(detail(), '37335'),
                             (detail().replace('Quintana de la Serena', 'Castuera'), '37404'),
                             (detail(state='No vigente'), '37404'),
                             (detail().replace('26/06/2014', '31/02/2014'), '37404')]:
            with self.assertRaises(ValueError):
                parse_detail(html, number)

    def test_manifest_and_refresh_preserve_document_grouping(self):
        m = load_manifest('quintana-de-la-serena')
        a = load_portal_adapter(m)
        self.assertIsInstance(a, QuintanaDeLaSerenaAyuntamientoAdapter)
        self.assertFalse(m.licencias.enabled)
        def fetch(session, url, capture, **kwargs):
            if kwargs.get('data'):
                self.assertEqual(kwargs['data'], {'municipioseleccionado': '154'})
                return INVENTORY
            n = url.rsplit('/', 1)[-1]
            return detail(n, 'PGM' if n == '37335' else 'PGM.M-' + n,
                          'En trámite' if n == '39696' else 'Vigente')
        with tempfile.TemporaryDirectory() as folder, patch.object(a, '_fetch', side_effect=fetch):
            output = Path(folder) / 'proyectos.jsonl'
            self.assertEqual(a.backfill_proyectos(output)['rows'], 3)
            first = output.read_text()
            a.update_proyectos(output, Path(folder) / 'state.json')
            self.assertEqual(first, output.read_text())
            rows = [json.loads(l) for l in first.splitlines()]
            for row in rows:
                n = row['id'].rsplit('-', 1)[-1]
                self.assertTrue(row['documentos'][1]['url'].endswith('/' + n))
            a.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
