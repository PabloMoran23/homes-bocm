"""Offline parser regressions; no captured evidence required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.fuente_del_maestre import (
    FuenteDelMaestreAyuntamientoAdapter, parse_inventory, parse_instrument,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

INVENTORY = '''<select id="PtofiguraMunicipio"><option selected value=""></option><option selected value="79">Fuente del Maestre</option></select>
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/37246','PGM');"><img alt="Vigente"></a>
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/40990','PPO');"><img alt="En trámite"></a>
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/37001','PEPCH');"><img alt="No vigente"></a>
<a href="form.pdf">Solicitud de licencia</a>'''
DETAIL = '''<table>
<tr><th>Figura urbanística</th><td>Plan General Municipal</td></tr>
<tr><th>Ámbito territorial</th><td>Fuente del Maestre</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Referencia</th><td>PGM</td></tr>
<tr><th>Fecha AD</th><td>27/04/2023</td></tr>
<tr><th>Fecha de publicación AD</th><td>13/12/2023</td></tr>
<tr id="filatramite1"><td>13/12/2023</td><td><a href="https://doe.juntaex.es/test.pdf">Publicación en DOE</a></td></tr>
<tr><td>memoria.pdf</td><td><a download="Memoria justificativa" href="/SITEX/ptofiguras/downloaddocumento/1"></a></td></tr>
<tr><td>planos.pdf</td><td><a download="Planos" href="/SITEX/ptofiguras/downloaddocumento/2"></a></td></tr>
</table><a href="licencia.pdf">Formulario</a>'''
URL = 'https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37246'


class ParserTests(unittest.TestCase):
    def test_current_inventory_and_disabled_history(self):
        items, excluded = parse_inventory(INVENTORY)
        self.assertEqual(len(items), 2)
        self.assertEqual(excluded, 1)
        self.assertEqual(items[1]['status'], 'En trámite')

    def test_municipality_filter_required(self):
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY.replace('value="79"', 'value="80"'))

    def test_pagination_fails_closed(self):
        for pager in ['<a href="?page=2" rel="next">2</a>', '<div class="paging">2</div>']:
            with self.assertRaises(ValueError):
                parse_inventory(INVENTORY + pager)

    def test_group_documents_and_distinct_dates(self):
        row = parse_instrument(DETAIL, URL, 'Vigente')
        self.assertEqual(row['fecha_aprob'], '2023-04-27')
        self.assertEqual(row['fecha_publicacion'], '2023-12-13')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['titulo'], 'Memoria justificativa')
        self.assertNotIn('fecha', row)
        self.assertNotIn('lat', row)
        self.assertNotIn('fase', row)

    def test_missing_dates_and_status_not_inferred(self):
        html = DETAIL.replace('Vigente', 'En trámite').replace('27/04/2023', '').replace('13/12/2023</td></tr>', '</td></tr>')
        row = parse_instrument(html, URL, 'En trámite')
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha_publicacion', row)
        self.assertEqual(row['estado_fuente'], 'En trámite')

    def test_wrong_municipality_and_status_rejected(self):
        for html in [DETAIL.replace('Fuente del Maestre', 'Fuente de Cantos'), DETAIL.replace('Vigente', 'No vigente')]:
            with self.assertRaises(ValueError):
                parse_instrument(html, URL, 'Vigente')

    def test_adapter_snapshot_and_manifest(self):
        manifest = load_manifest('fuente-del-maestre')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, FuenteDelMaestreAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, DETAIL, DETAIL.replace('Vigente', 'En trámite')]):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['count'], 2)
            self.assertEqual(rows[0]['codigo_ine'], '06054')
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['count'], 0)


if __name__ == '__main__':
    unittest.main()
