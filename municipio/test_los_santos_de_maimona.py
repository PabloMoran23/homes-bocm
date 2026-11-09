"""Offline parser contract tests; no dependency on uncommitted evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.los_santos_de_maimona import (
    LosSantosDeMaimonaAyuntamientoAdapter, parse_detail, parse_inventory,
    parse_municipality, MUNICIPALITY, ROOT,
)
from municipio.manifest import load_manifest

SELECTOR = '<select id="PtofiguraMunicipio"><option selected value=""></option><option selected value="167">Santos de Maimona, Los</option></select>'


def entry(key='40625', status='Vigente'):
    return f'''<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/{key}','Santos de Maimona, Los - PGM.ED-010');"><img alt="{status}">ED-010</a>'''


def detail(approval='29/01/2024'):
    return f'''<div id="divplaneamiento40625"><div id="infoplaneamiento40625"><table>
    <tr><th>Figura urbanística</th><td>Estudio de detalle RE-198 y RE-197</td></tr>
    <tr><th>Ámbito territorial</th><td>{MUNICIPALITY}</td><td class="campoconidsdemunicipiosparamapa">167</td></tr>
    <tr><th>Estado</th><td>Vigente</td></tr>
    <tr><th>Referencia</th><td>PGM.ED-010</td></tr>
    <tr><th>Fecha AD</th><td>{approval}</td></tr>
    <tr><th>Fecha de publicación AD</th><td>01/07/2024</td></tr></table>
    <div id="listadotramitesplaneamiento40625"><table><tr id="filatramite1"><td>01/07/2024</td><td><a href="https://doe.juntaex.es/pdfs/doe/2024/1260o/24081058.pdf">Publicación en DOE de la aprobación definitiva</a></td></tr></table></div>
    </div><a href="/SITEX/ptofiguras/downloaddocumento/123" download="Memoria - plan.pdf"></a>
    <a href="/SITEX/ptofiguras/downloaddocumento/123" download="Memoria - plan.pdf"></a>
    </div><a href="/SITEX/files/calificacion/FormularioAutorrellenable.pdf">Formulario</a>'''


class ParserTests(unittest.TestCase):
    def test_discovery_and_status_scope(self):
        self.assertEqual(parse_municipality(SELECTOR), '167')
        rows = parse_inventory(SELECTOR + entry() + entry() + entry('1', 'No vigente') + entry('2', 'En trámite'), '167')
        self.assertEqual(list(rows), ['40625'])

    def test_reject_wrong_municipality_and_unknown_status(self):
        for html in (SELECTOR.replace('value="167"', 'value="168"') + entry(),
                     SELECTOR + entry(status='Unknown'), SELECTOR):
            with self.assertRaises(ValueError):
                parse_inventory(html, '167')
        with self.assertRaises(ValueError):
            parse_municipality('<select></select>')

    def test_pagination_never_truncated(self):
        for control in ('<a rel="next" href="?page=2">2</a>', '<div class="paging">2</div>', '<a>Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(SELECTOR + entry() + control, '167')

    def test_dates_documents_grouping_and_provenance(self):
        url = ROOT + '/SITEX/ptofiguras/viewsigcat/40625'
        row = parse_detail(detail(), '40625', url, '167')
        self.assertEqual(row['fecha_aprob'], '2024-01-29')
        self.assertEqual(row['fecha_publicacion'], '2024-07-01')
        self.assertEqual(row['codigo_ine'], '06122')
        self.assertEqual(row['expediente'], 'PGM.ED-010')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['provenance_url'] == url for d in row['documentos']))
        self.assertEqual(row['tramites'][0]['fecha'], '2024-07-01')
        self.assertNotIn('lat', row)
        self.assertNotIn('fecha', row)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertIsNone(parse_detail(detail(''), '40625', url, '167')['fecha_aprob'])

    def test_detail_drift_rejected(self):
        for html in (detail().replace('>Vigente<', '>No vigente<'),
                     detail().replace('>167<', '>168<'), '<html>Error</html>',
                     detail().replace(MUNICIPALITY, 'Otro municipio')):
            with self.assertRaises(ValueError):
                parse_detail(html, '40625', ROOT, '167')

    def test_snapshot_is_atomic_on_failure(self):
        adapter = LosSantosDeMaimonaAyuntamientoAdapter('los-santos-de-maimona')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[SELECTOR, SELECTOR + entry(), '<html>Error</html>']):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(path, Path(folder) / 'state.json')
            self.assertEqual(path.read_text(), 'previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[SELECTOR, SELECTOR + entry(), detail()]):
                result = adapter.backfill_proyectos(path)
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(path.read_text())['id_origen'], '40625')
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('los-santos-de-maimona')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertIn('los_santos_de_maimona:', manifest.portal.adapter)


if __name__ == '__main__':
    unittest.main()
