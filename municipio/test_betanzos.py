import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.betanzos import (
    BetanzosAyuntamientoAdapter, SOURCE, discover_pxom, parse_pxom,
)
from municipio.manifest import load_manifest

DETAIL = 'https://concello.betanzos.es/portfolio-items/plan-xeral-de-ordenacion-urbana-do-concello-de-betanzos/'
INVENTORY = f'<div class="tab-pane"><a href="{DETAIL}"><img></a><a href="{DETAIL}">PXOM</a></div>'
PAGE = '''<div class="project-description">
<p><strong>“Revisión do Plan xeral de ordenación municipal de Betanzos, documento para aprobación inicial”,</strong> datado en xullo do 2021.</p>
<h4>Este documento foi aprobado polo Pleno do Concello o 15 de setembro de 2021.</h4>
<h4><a href="/wp-content/uploads/2021/10/dog.pdf">Diario Oficial de Galicia</a> de data 20 de outubro de 2021</h4>
<p>00. Indice. <a href="/wp-content/uploads/2021/10/indice.pdf">VER</a></p>
<p>01. Memoria. <a href="https://drive.google.com/drive/folders/memoria">VER</a></p>
<p><a href="https://drive.google.com/file/d/certificado/view">Certificado aprobación inicial Pleno</a></p>
<p>Formulario Alegacions-PXOM <a href="/formulario.pdf">VER</a></p>
<p><a href="https://evil.example/a.pdf">Documento ajeno</a></p>
</div><footer><a href="/unrelated.pdf">Other plan</a></footer>'''


class BetanzosTests(unittest.TestCase):
    def test_discovery_deduplicates_and_requires_inventory(self):
        self.assertEqual(discover_pxom(INVENTORY), [DETAIL])
        with self.assertRaises(ValueError):
            discover_pxom('<a href="/formulario.pdf">Licenzas</a>')

    def test_grouping_dates_and_provenance(self):
        row = parse_pxom(PAGE, DETAIL)
        self.assertEqual(row['codigo_ine'], '15009')
        self.assertEqual(row['fecha_acuerdo'], '2021-09-15')
        self.assertEqual(row['fecha_publicacion'], '2021-10-20')
        self.assertEqual(len(row['documentos']), 4)
        self.assertTrue(all(d['provenance_url'] == DETAIL for d in row['documentos']))
        self.assertTrue(any('Memoria' in d['titulo'] for d in row['documentos']))
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['geometry_status'], 'unavailable')
        for field in ['fecha_aprob', 'fecha_concesion', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, row)

    def test_no_dates_inferred_from_urls_or_document_month(self):
        page = PAGE.replace('Este documento foi aprobado polo Pleno do Concello o 15 de setembro de 2021.', '')
        page = page.replace('de data 20 de outubro de 2021', '')
        row = parse_pxom(page, DETAIL)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertNotIn('fecha_publicacion', row)

    def test_pagination_is_not_silently_truncated(self):
        for marker in ['<a rel="next" href="?page=2">2</a>', '<a href="/page/2">Seguinte</a>']:
            with self.assertRaises(ValueError):
                discover_pxom(INVENTORY + marker)
            with self.assertRaises(ValueError):
                parse_pxom(PAGE + marker, DETAIL)

    def test_missing_or_form_only_source_fails(self):
        for page in ['', '<div class="project-description">Not a plan</div>', PAGE.replace('.pdf', '.txt')]:
            with self.assertRaises(ValueError):
                parse_pxom(page, DETAIL)

    def test_adapter_writes_one_instrument_and_refreshes(self):
        adapter = BetanzosAyuntamientoAdapter('betanzos')
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, '_fetch', side_effect=[INVENTORY, PAGE, INVENTORY, PAGE]):
            output = Path(temp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            initial = output.read_text()
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(initial.splitlines()), 1)
            adapter.update_proyectos(output, Path(temp) / 'state.json')
            self.assertEqual(output.read_text(), initial)
            self.assertEqual(len(json.loads(initial)['documentos']), 4)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('betanzos')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'A Coruña')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'licencias.jsonl'
            result = BetanzosAyuntamientoAdapter('betanzos').backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
