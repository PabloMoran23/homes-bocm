import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villava import INVENTORY, VillavaAyuntamientoAdapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

PLAN_URL = 'https://www.villava.es/general/documentacion-del-plan-general-municipal/'
INVENTORY_HTML = '''<main><div class="contenido content"><a href="/news/documentacion-del-plan-general-municipal/">Plan General de Ordenación Urbana (PGOU), mapas y planos en detalle</a></div></main>'''
PLAN = '''<main><h2 class="titulo_prede">Documentación del Plan General Municipal</h2>
<div class="contenido content"><p>El Ayuntamiento de Villava, en sesión extraordinaria celebrada el día 12 de mayo de 2015, aprobó inicialmente el Plan General Municipal y el Estudio de Incidencia Ambiental.</p>
<p><a href="/wp-content/uploads///2016/acuerdo.pdf">Con fecha 25 de octubre de 2016, el Ayuntamiento Pleno acuerda:</a></p>
<p>PRIMERO.- Aprobar provisionalmente el Plan General Municipal de Villava –Atarrabia.</p>
<h4>Plan Urbanístico Municipal (Memoria Justificativa)</h4><p><a href="/wp-content/uploads///2015/Memoria.pdf">Memoria</a><a href="/wp-content/uploads/2015/Memoria.pdf">Memoria duplicada</a></p>
<h4>Planos</h4><p><a href="/wp-content/uploads/2015/P1.pdf">P1 Clasificación</a></p></div></main>'''


class VillavaParserTests(unittest.TestCase):
    def test_inventory_discovery_and_fail_closed(self):
        self.assertEqual(VillavaAyuntamientoAdapter.discover_plan(INVENTORY_HTML),
                         'https://www.villava.es/news/documentacion-del-plan-general-municipal/')
        for html in ('<html>error</html>', INVENTORY_HTML.replace('/news/', 'https://example.org/'),
                     INVENTORY_HTML + '<a rel="next" href="?page=2">Next</a>'):
            with self.assertRaises(ValueError):
                VillavaAyuntamientoAdapter.discover_plan(html)

    def test_one_instrument_documents_and_date_semantics(self):
        rows = VillavaAyuntamientoAdapter.parse_plan(PLAN, PLAN_URL)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['acuerdos_documentados'][0]['fecha_acuerdo'], '2015-05-12')
        self.assertEqual(row['acuerdos_documentados'][1]['fecha_acuerdo'], '2016-10-25')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertNotIn('fase', row)
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['documentos'][1]['url_pagina'], PLAN_URL)

    def test_reject_partial_or_changed_detail(self):
        for html in (PLAN.replace('PRIMERO.-', 'Changed'), PLAN.replace('<h4>Planos</h4>', ''),
                     PLAN.replace('2016', 'XXXX'), PLAN.replace('/2015/P1.pdf', '/2015/P1.html'),
                     PLAN.replace('</div>', '<a href="?page=2">Siguiente</a></div>')):
            with self.assertRaises(ValueError):
                VillavaAyuntamientoAdapter.parse_plan(html, PLAN_URL)

    def test_manifest_contract_and_refresh(self):
        manifest = load_manifest('villava')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[(INVENTORY_HTML, INVENTORY), (PLAN, PLAN_URL)]):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '31258')
            licences = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(licences)['status'], 'disabled')
            self.assertEqual(licences.read_text(), '')


if __name__ == '__main__':
    unittest.main()
