"""Offline parser/transport tests; no live requests or evidence fixtures required."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from municipio.adapters.santaella import (
    BASE, INVENTORY, SantaellaAyuntamientoAdapter, parse_detail, parse_page,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(code='32790', total=1):
    return {'iTotalDisplayRecords': total, 'iTotalRecords': total,
            'aaData': [['CÓRDOBA', 'SANTAELLA', 'PGOU', '26/10/16', 'LOUA', '',
                        f'<a class="docuPlan" name="{code}" href="#"></a>', '']]}


def detail(code='32790'):
    entries = [{'nombre': 'Normas', 'enlace': '<a class="descargaDoc" href="descargaDocumentos.jsf?doc=12"></a>', 'clave': k}
               for k in ['106083', '106083-Normas']]
    return f'''<input name="codFigura" value="{code}"><table>
<tr><td><span class="area-filter-label">Figura:</span></td><td>PGOU - Plan General de Ordenación Urbanística</td></tr>
<tr><td><span class="area-filter-label">Objeto:</span></td><td>2016</td></tr>
<tr><td><span class="area-filter-label">Ámbito Territorial:</span></td><td>MUNICIPAL - Municipal SANTAELLA</td></tr>
<tr><td><span class="area-filter-label">Fecha de Aprobación:</span></td><td>26/10/16</td></tr>
</table><script>var mapa={json.dumps(entries)};</script>'''


RESULT = '''<form action="/situadifusion/pages/result.jsf">
<input type="hidden" name="javax.faces.ViewState" value="view">
<input type="hidden" name="codigosMunicipios" value="14060">
<a id="j_id6:tipoPlaneamiento"></a></form>'''


class ParserTests(unittest.TestCase):
    def test_group_documents_and_date_semantics(self):
        _, instruments = parse_page(page())
        row = parse_detail(detail(), instruments[0])
        self.assertEqual(row['fecha_aprob'], '2016-10-26')
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(len(row['documentos'][0]['grupos_fuente']), 2)
        self.assertEqual(row['documentos'][0]['url'], BASE + 'descargaDocumentos.jsf?doc=12')
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry', 'fase']:
            self.assertNotIn(field, row)

    def test_reject_wrong_municipality_and_missing_map(self):
        payload = page()
        payload['aaData'][0][1] = 'LA GUIJARROSA'
        with self.assertRaises(ValueError):
            parse_page(payload)
        instrument = parse_page(page())[1][0]
        for html in ['<html>403</html>', detail('999'), detail().split('<script>')[0],
                     detail().replace('Municipal SANTAELLA', 'Municipal OTRA')]:
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                parse_detail(html, instrument)

    def test_no_execution_of_javascript(self):
        instrument = parse_page(page())[1][0]
        with self.assertRaises(ValueError):
            parse_detail(detail().replace('var mapa=[', 'var mapa=alert(1);['), instrument)

    def test_manifest_contract(self):
        m = load_manifest('santaella')
        self.assertIsInstance(load_portal_adapter(m), SantaellaAyuntamientoAdapter)
        raw = load_yaml(m.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('14060', 'Córdoba'))
        for key, field in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[key][field], False)

    def test_pagination_and_multiple_details(self):
        adapter = SantaellaAyuntamientoAdapter('santaella')
        offsets = []
        def request(session, method, url, capture, **kwargs):
            if url == INVENTORY:
                offset = kwargs['data']['iDisplayStart']
                offsets.append(offset)
                payload = page(str(offset + 1), 2)
                return SimpleNamespace(json=lambda: payload)
            return SimpleNamespace(text=detail(kwargs['data']['codFigura']))
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_open_inventory', return_value=SimpleNamespace(text=RESULT)), patch.object(adapter, '_request', side_effect=request):
            out = Path(tmp) / 'out.jsonl'
            report = adapter.backfill_proyectos(out)
            self.assertEqual(offsets, [0, 1])
            self.assertEqual(report['count'], 2)
            self.assertEqual(len(out.read_text().splitlines()), 2)

    def test_repeated_page_fails_without_replacing_output(self):
        adapter = SantaellaAyuntamientoAdapter('santaella')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_open_inventory', return_value=SimpleNamespace(text=RESULT)), patch.object(adapter, '_request', return_value=SimpleNamespace(json=lambda: page(total=2))):
            out = Path(tmp) / 'out.jsonl'
            out.write_text('previous\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            report = SantaellaAyuntamientoAdapter('santaella').backfill_licencias(out)
            self.assertTrue(report['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
