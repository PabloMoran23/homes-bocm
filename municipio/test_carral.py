import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.carral import CarralAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

FIXTURE = '''<article><div class="entry-content">
<p>Aprobación inicial do plan xeral de ordenación municipal (PXOM) do Concello de Carral.</p>
<a href="/wp-content/uploads/Instancia.pdf">Instancia alegacions pxom</a>
<a href="/wp-content/uploads/anuncio.pdf">Ampliación información pública</a>
<ol><li>MEMORIA <a href="/wp-content/uploads/memo.pdf">I2-Cl-D01-MEMO</a></li>
<li>NORMATIVA <a href="/wp-content/uploads/norm.pdf">I2-Cl-D08-NORM</a>
<a href="/wp-content/uploads/memo.pdf">MEMO repetido</a>
<a href="https://example.org/unrelated.pdf">Ajeno</a></li></ol>
<p>PXOM aprobado inicialmente. Upload 2016/04; esto no es una fecha de acuerdo.</p>
</div></article><footer><a href="/footer.pdf">Footer</a></footer>'''


class CarralTests(unittest.TestCase):
    def test_groups_instrument_and_retains_documents(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15021')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual([d['tipo'] for d in row['documentos']],
                         ['anuncio_tramitacion', 'documento_plan', 'documento_plan'])
        self.assertTrue(all(d['inventory_url'] == SOURCE_URL for d in row['documentos']))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon'):
            self.assertNotIn(key, row)

    def test_missing_or_unrelated_inventory_fails(self):
        for html in ('', '<article>Licencia: formulario</article>',
                     FIXTURE.replace('I2-Cl-D08-NORM', 'Documento'),
                     FIXTURE.replace('Concello de Carral', 'Concello de Otro')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_never_silently_truncated(self):
        for extra in ('<a rel="next" href="/page/2">2</a>',
                      '<div class="page-links">1 2</div>'):
            with self.assertRaises(ValueError):
                parse_inventory(FIXTURE + extra)
        with self.assertRaises(ValueError):
            parse_inventory(FIXTURE.replace('</ol>', '</ol><a href="?page=2">Seguinte</a>'))

    def test_manifest_and_live_entrypoint(self):
        manifest = load_manifest('carral')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '15021')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE_URL, text=FIXTURE)
        with tempfile.TemporaryDirectory() as directory, patch(
            'municipio.adapters.carral.requests.get', return_value=response
        ) as fetch:
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 3)
            fetch.assert_called_once()
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')

    def test_failed_request_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rows.jsonl'
            output.write_text('previous')
            response = Mock(url=SOURCE_URL, text='<html>maintenance</html>')
            with patch('municipio.adapters.carral.requests.get', return_value=response):
                with self.assertRaises(ValueError):
                    CarralAyuntamientoAdapter('carral').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous')


if __name__ == '__main__':
    unittest.main()
