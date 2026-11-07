"""Offline parser/contract regressions. Fixtures model SITEX's observed HTML."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.montijo import (
    BASE, MontijoAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.entity_policy import classify
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

TREE = '''<select id="PtofiguraMunicipio"><option value="" selected />
<option value="123" selected>Montijo</option></select>
<ul><li><a class="unenlaceafiguradeplaneamiento" title="Revisión de normas"
onclick="addTab('/SITEX/ptofiguras/viewsigcat/34499','Montijo - NNSS.R-002');">NNSS.R-002</a>
<ul><li><a class="unenlaceafiguradeplaneamiento" title="Modificación"
onclick="addTab('/SITEX/ptofiguras/viewsigcat/40866','Montijo - NNSS.R-002.M-049');">M-049</a></li></ul>
</li></ul>'''
DETAIL = '''<div id="infoplaneamiento34499"><table>
<tr><th>Figura urbanística</th><td>REVISION DE NORMAS SUBSIDIARIAS</td></tr>
<tr><th>Ámbito territorial</th><td>Montijo</td><td hidden>123</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Referencia</th><td>NNSS.R-002</td></tr>
<tr><th>Fecha AD</th><td>06/05/1991</td></tr>
<tr><th>Fecha de publicación AD</th><td>20/08/1991</td></tr>
<tr><th>Diario de publicación AD</th><td>BOP</td></tr></table>
<table><tr id="filatramite1"><td>20/08/1991</td><td><a href="https://example.org/bop.pdf">Publicación en BOP de la aprobación definitiva</a></td></tr></table></div>
<div id="archivosplaneamiento34499"><table>
<tr><td>Memoria</td><td><a download="Memoria justificativa" href="/SITEX/ptofiguras/downloaddocumento/11371"></a></td></tr>
<tr><td>Plano</td><td><a href="/SITEX/ptofiguras/downloaddocumento/11372"></a></td></tr>
<tr><td>Memoria duplicada</td><td><a href="/SITEX/ptofiguras/downloaddocumento/11371"></a></td></tr>
</table></div><nav><a href="/SITEX/pages/modelospgm">Modelo de licencia</a></nav>'''


class MontijoTests(unittest.TestCase):
    def setUp(self):
        self.items = parse_inventory(TREE)

    def test_nested_inventory_not_one_record_per_document(self):
        self.assertEqual([r['source_id'] for r in self.items], ['34499', '40866'])
        row = parse_detail(DETAIL, self.items[0])
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][-1]['titulo'], 'Plano')
        self.assertEqual(row['documentos'][1]['source_url'], self.items[0]['url'])
        self.assertEqual(row['documentos'][1]['url'], BASE + '/SITEX/ptofiguras/downloaddocumento/11371')
        self.assertNotIn('Modelo', json.dumps(row))

    def test_dates_and_no_inferred_geometry_or_phase(self):
        row = parse_detail(DETAIL, self.items[0])
        self.assertEqual(classify(row)['entity_type'], 'expediente')
        self.assertEqual(row['fecha_aprob'], '1991-05-06')
        self.assertEqual(row['fecha_publicacion'], '1991-08-20')
        self.assertEqual(row['tramites'][0]['fecha'], '1991-08-20')
        for key in ['fecha', 'fecha_acuerdo', 'lat', 'lon', 'coordinates', 'fase']:
            self.assertNotIn(key, row)
        no_dates = DETAIL.replace('06/05/1991', '').replace('20/08/1991', '')
        row = parse_detail(no_dates, self.items[0])
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha_publicacion', row)

    def test_isolation_and_identity(self):
        for html, item in [(DETAIL, self.items[1]), (DETAIL.replace('Montijo', 'Badajoz'), self.items[0])]:
            with self.assertRaises(ValueError):
                parse_detail(html, item)
        for html in ['', TREE.replace('value="123" selected', 'value="17" selected'), TREE.replace('Montijo - NNSS', 'Badajoz - NNSS')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_truncating(self):
        for extra in ['<a rel="next" href="/next">Más</a>', '<div class="paging">2</div>', '<a href="?page=2">2</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(TREE + extra)
            with self.assertRaises(ValueError):
                parse_detail(DETAIL + extra, self.items[0])

    def test_missing_documents_is_explicit(self):
        html = DETAIL[:DETAIL.index('<div id="archivos')].replace('<a href="https://example.org/bop.pdf">', '').replace('</a>', '')
        row = parse_detail(html, self.items[0])
        self.assertEqual(row['documentos'], [])
        self.assertEqual(row['document_coverage'], 'metadata_only')

    def test_manifest_and_disabled_licences(self):
        m = load_manifest('montijo')
        raw = load_yaml(m.path)
        self.assertEqual((raw['codigo_ine'], m.nombre, m.provincia), ('06088', 'Montijo', 'Badajoz'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(m.licencias.enabled)
        a = load_portal_adapter(m)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'licencias.jsonl'
            self.assertTrue(a.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')

    def test_failed_detail_does_not_replace_existing_output(self):
        a = MontijoAyuntamientoAdapter('montijo')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            with patch.object(a, '_fetch', side_effect=[TREE, DETAIL, '<html>broken</html>']):
                with self.assertRaises(ValueError):
                    a.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
