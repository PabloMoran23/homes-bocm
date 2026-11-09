import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.talavera_la_real import (
    TalaveraLaRealAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest

INVENTORY = '''<select id="PtofiguraMunicipio"><option selected value="176">Talavera la Real</option></select>
<a class="unenlaceafiguradeplaneamiento" title="Plan de prueba" onclick="addTab('/SITEX/ptofiguras/viewsigcat/1','Talavera la Real - NNSS.R-001');">Plan</a>'''
DETAIL = '''<table class="juntaex">
<tr><th>Figura urbanística</th><td>Revisión Normas Subsidiarias</td></tr>
<tr><th>Ámbito territorial</th><td>Talavera la Real</td></tr>
<tr><th>Referencia</th><td>NNSS.R-001</td></tr>
<tr><th>Estado</th><td>No vigente</td></tr>
<tr><th>Fecha AD</th><td>24/08/1993</td></tr>
<tr><th>Fecha de publicación AD</th><td>09/12/1993</td></tr>
</table><table id="tablaCalificacionplaneamientostramit">
<tr id="filatramite1"><td>01/05/1991</td><td><a href="https://example.org/boletin.pdf">Información pública de aprobación inicial</a></td></tr>
</table><div id="archivosplaneamiento1">
<a href="/SITEX/ptofiguras/downloaddocumento/12" download="Memoria.pdf">PDF</a>
<a href="/SITEX/ptofiguras/downloaddocumento/13" download="Planos.pdf">PDF</a>
<a href="/SITEX/ptofiguras/downloaddocumento/12" download="Memoria.pdf">PDF</a>
</div><a href="/SITEX/files/formulario.pdf">Solicitud de licencia</a>'''


class TalaveraTests(unittest.TestCase):
    def test_inventory_identity_dedup_and_empty(self):
        self.assertEqual(len(parse_inventory(INVENTORY + INVENTORY.split('</select>')[1])), 1)
        for bad in ('<html>Login</html>', INVENTORY.replace('176', '17'), INVENTORY.split('<a')[0]):
            with self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_pagination_fails_closed(self):
        for marker in ('<div class="paging">2</div>', '<a rel="next" href="?page=2">Next</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(INVENTORY + marker)

    def test_dates_documents_and_no_invented_geometry(self):
        entry = parse_inventory(INVENTORY)[0]
        row = parse_detail(DETAIL, entry)
        self.assertEqual(row['fecha_aprob'], '1993-08-24')
        self.assertEqual(row['fecha_publicacion'], '1993-12-09')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(row['tramites'][0]['fecha'], '1991-05-01')
        self.assertEqual(len(row['documentos']), 3)
        self.assertTrue(all(d['procedencia'] == entry['url'] for d in row['documentos']))
        self.assertFalse(any('formulario' in d['url'] for d in row['documentos']))
        self.assertEqual(row['estado_fuente'], 'No vigente')
        self.assertNotIn('fase', row)
        for field in ('lat', 'lon', 'geometry', 'fecha'):
            self.assertIsNone(row[field])
        other = dict(entry, sitex_id='2', referencia='NNSS.M-002', url=entry['url'] + '2')
        second = parse_detail(DETAIL.replace('NNSS.R-001', 'NNSS.M-002').replace('downloaddocumento/12', 'downloaddocumento/99'), other)
        self.assertNotEqual(row['id'], second['id'])
        self.assertFalse(any(d['url'].endswith('/99') for d in row['documentos']))

    def test_missing_dates_not_inferred_from_procedure(self):
        row = parse_detail(DETAIL.replace('24/08/1993', '').replace('09/12/1993', ''), parse_inventory(INVENTORY)[0])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(len(row['tramites']), 1)

    def test_detail_identity_and_invalid_date(self):
        for bad in (DETAIL.replace('Talavera la Real', 'Talavera de la Reina'),
                    DETAIL.replace('NNSS.R-001', 'OTHER'), DETAIL.replace('24/08/1993', '31/02/1993')):
            with self.assertRaises(ValueError):
                parse_detail(bad, parse_inventory(INVENTORY)[0])

    def test_live_contract_snapshot_and_disabled_licences(self):
        adapter = TalaveraLaRealAyuntamientoAdapter('talavera-la-real')
        with tempfile.TemporaryDirectory() as tmp:
            output, state = Path(tmp) / 'proyectos.jsonl', Path(tmp) / 'state.json'
            landing = '<select id="PtofiguraMunicipio"><option value="176">Talavera la Real</option></select>'
            with patch.object(adapter, '_fetch', side_effect=[landing, INVENTORY, DETAIL]):
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['live_records'], 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '06128')
            original = output.read_text()
            with patch.object(adapter, '_fetch', side_effect=[landing, INVENTORY, ValueError('network')]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)
            lic = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.update_licencias(lic, state)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')
            self.assertFalse(state.exists())

    def test_manifest(self):
        manifest = load_manifest('talavera-la-real')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
