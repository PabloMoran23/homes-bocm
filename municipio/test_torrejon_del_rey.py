"""Offline contract/semantic tests; live captures remain local under evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.torrejon_del_rey import (
    NAME, SOURCE, ROOT, TorrejonDelReyAyuntamientoAdapter,
    municipality_filter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

URL = ROOT + '/registros/pau/test-sector'
FILTER = '<select name="municipio"><option value="1007">-Torrejón del Rey</option></select>'
DETAIL = '''<article class="node--type-programa-actuacion-urbanizadora" data-history-node-id="123">
<div class="field--name-title">P.A.U. SECTOR DE PRUEBA</div>
<div class="field--name-municipios-clm"><ul><li>GUADALAJARA</li><li>Torrejón del Rey</li></ul></div>
<div class="field--name-field-fecha-aprobacion"><div class="field__item"><time datetime="2011-04-13T12:00:00Z">13/04/2011</time></div></div>
<div class="field--name-field-publicacion-docm"><div class="field__item"><time datetime="2010-03-26T12:00:00Z">26/03/2010</time></div></div>
<div class="field--name-field-datos-inscripcion"><div class="field__item">Libro 1, Folio 255</div></div>
<div class="field--name-field-observaciones"><div class="field__item">Resolución 23/11/2012. Inscrito 03/04/2013.</div></div>
<a href="/files/memoria.pdf">Memoria</a><a href="/files/planos.pdf">Planos</a><a href="/files/memoria.pdf">Memoria repetida</a>
</article>'''


def inventory(link='/registros/pau/test-sector', pager=''):
    return f'''<table class="views-table"><tbody><tr>
    <td class="views-field-title"><a href="{link}">P.A.U. SECTOR DE PRUEBA</a></td>
    <td class="views-field-municipios-clm">{NAME}</td>
    </tr></tbody></table>{pager}'''


class TorrejonTests(unittest.TestCase):
    def test_manifest_contract_and_loader(self):
        m = load_manifest('torrejon-del-rey')
        raw = load_yaml(m.path)
        self.assertEqual((raw['codigo_ine'], m.nombre, m.provincia), ('19280', NAME, 'Guadalajara'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(m.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(m), TorrejonDelReyAyuntamientoAdapter)

    def test_filter_uses_name_not_hardcoded_taxonomy(self):
        self.assertEqual(municipality_filter(FILTER.replace('1007', '9999')), '9999')
        with self.assertRaises(ValueError):
            municipality_filter(FILTER.replace(NAME, 'Torrejón de Ardoz'))

    def test_dates_have_separate_meanings(self):
        row = parse_project(DETAIL, URL)
        self.assertEqual(row['fecha_aprob'], '2011-04-13')
        self.assertEqual(row['fecha_publicacion'], '2010-03-26')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['fase'])
        self.assertIn('03/04/2013', row['observaciones'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['origen'], 'registro_autonomico')

    def test_documents_grouped_and_deduplicated(self):
        row = parse_project(DETAIL, URL)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['url'], ROOT + '/files/memoria.pdf')
        self.assertEqual(row['id'], parse_project(DETAIL, URL + '-renamed')['id'])

    def test_optional_dates_and_required_provenance(self):
        row = parse_project(DETAIL.replace('field-publicacion-docm', 'absent'), URL)
        self.assertIsNone(row['fecha_publicacion'])
        for broken in [DETAIL.replace(NAME, 'Torrejón de Ardoz'), DETAIL.replace('GUADALAJARA', 'MADRID'),
                       DETAIL.replace('field-datos-inscripcion', 'absent'), '<a>Solicitud licencia de obra</a>',
                       DETAIL.replace('2011-04-13T12:00:00Z', '2011-02-30T12:00:00Z')]:
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                parse_project(broken, URL)

    def test_inventory_requires_municipal_instruments(self):
        for html in ['', inventory().replace(NAME, 'Guadalajara'),
                     inventory().replace('P.A.U. SECTOR DE PRUEBA', 'Modelo solicitud licencia'),
                     inventory('https://unrelated.example/project')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE + '?municipio=1007')
        with self.assertRaises(ValueError):
            parse_inventory(inventory(pager='<a rel="next" href="?page=1">Next</a>'), SOURCE + '?municipio=1007')

    def test_live_method_traverses_pages_and_deduplicates(self):
        page0 = SOURCE + '?municipio=1007'
        page1 = SOURCE + '?municipio=1007&page=1'
        pages = {SOURCE: FILTER, page0: inventory(pager='<nav class="pager"><a href="?municipio=1007&amp;page=1">2</a></nav>'),
                 page1: inventory(), URL: DETAIL}
        adapter = TorrejonDelReyAyuntamientoAdapter('torrejon-del-rey')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'out.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda s, u: pages[u]) as fetch:
                result = adapter.backfill_proyectos(out)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(fetch.call_count, 4)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '19280')
            pages[page1] = '<html>source unavailable</html>'
            out.unlink()
            with patch.object(adapter, '_fetch', side_effect=lambda s, u: pages[u]), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            result = TorrejonDelReyAyuntamientoAdapter('torrejon-del-rey').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
