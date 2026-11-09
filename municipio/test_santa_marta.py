"""Offline parser contracts. Synthetic markup exercises semantics, not live counts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_marta import (
    SantaMartaAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory():
    return '''<select id="PtofiguraMunicipio"><option selected value="166">Santa Marta</option></select>
    <a onclick="addTab('/SITEX/ptofiguras/viewsigcat/1','Santa Marta - PGM');">PGM - V</a>
    <a onclick="addTab('/SITEX/ptofiguras/viewsigcat/2','Santa Marta - PGM.M-001');">M-001 - TR</a>
    <a onclick="addTab('/SITEX/ptofiguras/viewsigcat/3','Santa Marta - NNSS');">NNSS - NV</a>'''


def detail():
    return '''<div id="divplaneamiento2"><div id="infoplaneamiento2"><table>
    <tr><th>Figura urbanística</th><td>Modificación del PGM</td></tr>
    <tr><th>Ámbito territorial</th><td>Santa Marta</td><td class="campoconidsdemunicipiosparamapa">166</td></tr>
    <tr><th>Estado</th><td>En trámite</td></tr>
    <tr><th>Referencia</th><td>PGM.M-001</td></tr>
    <tr><th>Fecha AD</th><td>07/04/2022</td></tr>
    <tr><th>Fecha de publicación AD</th><td></td></tr>
    <tr id="filatramite1"><td>12/04/2021</td><td><a href="http://doe.juntaex.es/a.pdf">Información pública de la aprobación inicial en DOE</a></td></tr>
    </table></div><a download="Memoria" href="/SITEX/ptofiguras/downloaddocumento/42"></a>
    <a download="Memoria" href="/SITEX/ptofiguras/downloaddocumento/42"></a></div>'''


class SantaMartaTests(unittest.TestCase):
    def test_inventory_deduplicates_and_excludes_superseded(self):
        html = inventory()
        self.assertEqual([r['sitex_id'] for r in parse_inventory(html + html)], ['1', '2'])

    def test_wrong_municipality_empty_and_unknown_state_rejected(self):
        for html in ['', inventory().replace('selected ', ''),
                     inventory().replace('Santa Marta</option>', 'Santa Marta de Magasca</option>'),
                     inventory().replace('PGM - V', 'PGM - X')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected_on_inventory_and_detail(self):
        page = '<a href="?page=2" rel="next">Siguiente</a>'
        with self.assertRaises(ValueError):
            parse_inventory(inventory() + page)
        with self.assertRaises(ValueError):
            parse_detail(detail() + page, parse_inventory(inventory())[1])

    def test_dates_status_and_documents_are_not_conflated(self):
        row = parse_detail(detail(), parse_inventory(inventory())[1])
        self.assertEqual(row['fecha_aprob'], '2022-04-07')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(row['estado_fuente'], 'En trámite')
        self.assertEqual(row['tramites'][0]['fecha'], '2021-04-12')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['titulo'], 'Memoria')
        self.assertIsNone(row['geometry'])
        published = detail().replace('<th>Fecha de publicación AD</th><td></td>', '<th>Fecha de publicación AD</th><td>23/08/2022</td>')
        self.assertEqual(parse_detail(published, parse_inventory(inventory())[1])['fecha_publicacion'], '2022-08-23')

    def test_mismatched_or_missing_detail_rejected(self):
        for html in ['', detail().replace('<td>Santa Marta</td>', '<td>Otro municipio</td>'),
                     detail().replace('<td>En trámite</td>', '<td>Vigente</td>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, parse_inventory(inventory())[1])

    def test_manifest_resolves_and_licences_disabled(self):
        manifest = load_manifest('santa-marta')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), SantaMartaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            with patch('requests.Session', side_effect=AssertionError('No network for licences')):
                self.assertEqual(SantaMartaAyuntamientoAdapter('santa-marta').backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')

    def test_failure_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous\n')
            with patch('municipio.adapters.santa_marta.parse_detail', side_effect=ValueError('changed detail')):
                with patch('requests.Session') as session:
                    session.return_value.__enter__.return_value.request.return_value.text = inventory()
                    with self.assertRaises(ValueError):
                        SantaMartaAyuntamientoAdapter('santa-marta').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous\n')


if __name__ == '__main__':
    unittest.main()
