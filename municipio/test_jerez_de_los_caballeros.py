"""Offline semantic/parser tests; run with unittest, no fixture downloads."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.jerez_de_los_caballeros import (
    JerezDeLosCaballerosAyuntamientoAdapter, parse_inventory, parse_detail,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.entity_policy import classify

SELECT = '<select id="PtofiguraMunicipio"><option value="98">Jerez de los Caballeros</option></select>'


def link(ident='1', ref='PGM', state='V', name='Jerez de los Caballeros'):
    return f'''<a class="unenlaceafiguradeplaneamiento" title="Plan de prueba"
    onclick="addTab('/SITEX/ptofiguras/viewsigcat/{ident}','{name} - {ref}');" href="#">{ref} - {state}</a>'''


DETAIL = '''<div id="divplaneamiento1"><div id="infoplaneamiento1"><table>
<tr><th>Figura urbanística</th><td>Plan General Municipal</td></tr>
<tr><th>Ámbito territorial</th><td>Jerez de los Caballeros</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Fecha AD</th><td>27/04/2023</td></tr>
<tr><th>Fecha de publicación AD</th><td>15/06/2023</td></tr>
<tr><th>Diario de publicación AD</th><td>DOE</td></tr>
<tr id="filatramite1"><td>15/06/2023</td><td><a href="https://doe.juntaex.es/plan.pdf">Publicación en DOE</a></td></tr>
</table></div><div id="archivosplaneamiento1">
<a download="Memoria" href="/SITEX/ptofiguras/downloaddocumento/10"></a>
<a download="Memoria" href="/SITEX/ptofiguras/downloaddocumento/10"></a>
<a download="Plano" href="/SITEX/ptofiguras/downloaddocumento/11"></a>
</div></div>'''


class ParserTests(unittest.TestCase):
    def item(self):
        return parse_inventory(SELECT + link())[0]

    def test_inventory_deduplicates_and_excludes_inactive_and_territorial(self):
        rows = parse_inventory(SELECT + link() + link() + link('2', state='NV') +
                               link('3', ref='PE-001.M-001', state='TR') + link('4', name='Plan Territorial'))
        self.assertEqual([r['sitex_id'] for r in rows], ['1', '3'])
        self.assertEqual(rows[1]['referencia_inventario'], 'PE-001.M-001')

    def test_dates_and_documents_remain_in_one_instrument(self):
        row = parse_detail(DETAIL, self.item())
        self.assertEqual(row['fecha_aprob'], '2023-04-27')
        self.assertEqual(row['fecha_publicacion'], '2023-06-15')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['tramites'][0]['fecha'], '2023-06-15')
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '06070')
        self.assertEqual(classify(row)['entity_type'], 'expediente')
        self.assertEqual(row['expediente'], 'SITEX:1')

    def test_pending_never_invents_approval(self):
        item = parse_inventory(SELECT + link(state='TR'))[0]
        html = DETAIL.replace('Vigente', 'En trámite').replace('27/04/2023', '').replace('15/06/2023</td></tr>', '</td></tr>')
        row = parse_detail(html, item)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['estado'], 'En trámite')
        self.assertNotIn('fase', row)

    def test_explicit_empty_procedures_supported(self):
        start = DETAIL.index('<tr id="filatramite1">')
        end = DETAIL.index('</tr>', start) + len('</tr>')
        html = DETAIL[:start] + '<tr><td>No se han definido trámites hasta el momento</td></tr>' + DETAIL[end:]
        self.assertEqual(parse_detail(html, self.item())['tramites'], [])
        with self.assertRaises(ValueError):
            parse_detail(html.replace('No se han definido trámites', 'Changed layout'), self.item())

    def test_fail_closed_on_pagination_wrong_municipality_or_layout(self):
        for html in [SELECT + link() + '<a href="?page=2">Siguiente</a>',
                     SELECT.replace('value="98"', 'value="99"') + link(),
                     SELECT + link().replace('addTab', 'openNew'), SELECT]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        for html in [DETAIL.replace('Jerez de los Caballeros', 'Otro municipio'),
                     DETAIL.replace('Vigente', 'No vigente'), '<html>Unavailable</html>']:
            with self.assertRaises(ValueError):
                parse_detail(html, self.item())

    def test_snapshot_failure_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            adapter = JerezDeLosCaballerosAyuntamientoAdapter('jerez-de-los-caballeros')
            with patch('municipio.adapters.jerez_de_los_caballeros.requests.Session') as session:
                session.return_value.__enter__.return_value.get.side_effect = RuntimeError('offline')
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')
            self.assertEqual(adapter.backfill_licencias(Path(d) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('jerez-de-los-caballeros')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '06070')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
