import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.lodosa import LodosaAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return '''<main id="content"><h1>Proyectos Europeos del Ayuntamiento de Lodosa</h1>
    <div class="vc_row"><h3>PROYECTO 1 / RESTAURACIÓN MEDIOAMBIENTAL TORRE</h3>
    <ul><li>Beneficiario: <strong>AYUNTAMIENTO DE LODOSA</strong></li></ul><p>Importe de la ayuda: 57.095,98 euros</p>
    <p>ADENDA 19/11/2025</p><p>Datos de acceso: EXCLUDED</p>
    <table><tbody><tr><td>Subproyecto</td><td>C14.I01</td><td>Descripción original</td></tr></tbody></table>
    <a href="/convenio.pdf">Convenio</a><a href="/adenda.pdf">Adenda 19/11/2025</a>
    <a href="/adenda.pdf">Adenda repetida</a></div>
    <div class="vc_row"><h3>PROYECTO 2 / MEJORAS EN AUDITORIO</h3>
    <ul><li>Beneficiario: <strong>AYUNTAMIENTO DE LODOSA</strong></li></ul>
    <table><tbody><tr><td>Subproyecto</td><td>C24.I2.P01</td></tr></tbody></table></div>
    <a href="/formulario.pdf">Solicitud de licencia</a></main>'''


class LodosaTests(unittest.TestCase):
    def test_grouping_provenance_dates_and_no_access_text(self):
        rows = LodosaAyuntamientoAdapter.parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[1]['documentos'], [])
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://www.lodosa.es/convenio.pdf')
        self.assertEqual(rows[0]['identificacion_fuente']['Subproyecto'], 'C14.I01 | Descripción original')
        self.assertNotIn('EXCLUDED', json.dumps(rows))
        for row in rows:
            for field in ('fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(row[field])
        reordered = fixture().replace('PROYECTO 1 /', 'PROYECTO 9 /')
        self.assertEqual(rows[0]['id'], LodosaAyuntamientoAdapter.parse_inventory(reordered)[0]['id'])

    def test_reject_incomplete_or_changed_inventory(self):
        bad = [fixture().replace('id="content"', 'id="other"'),
               fixture().replace('Subproyecto', 'Otro'),
               fixture().replace('AYUNTAMIENTO DE LODOSA', 'OTRO'),
               fixture().replace('RESTAURACIÓN MEDIOAMBIENTAL TORRE', 'Solicitud de licencia'),
               fixture().replace('</main>', '<a rel="next" href="/page/2">2</a></main>'),
               fixture().replace('</main>', '<a href="/page/2">Siguiente</a></main>')]
        for html in bad:
            with self.subTest(html=html[-90:]), self.assertRaises(ValueError):
                LodosaAyuntamientoAdapter.parse_inventory(html)

    def test_manifest_and_atomic_extraction(self):
        manifest = load_manifest('lodosa')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('31157', 'Navarra'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous')
            with patch('municipio.adapters.lodosa.requests.Session') as session:
                response = Mock(content=b'<html>Missing source</html>')
                session.return_value.__enter__.return_value.get.return_value = response
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), 'previous')
                response.content = fixture().encode()
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
                self.assertEqual(result['rows'], 2)
                self.assertEqual(len(output.read_text().splitlines()), 2)
                session.return_value.__enter__.return_value.get.assert_called_with(SOURCE, timeout=30)
            lic = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_text(), '')


if __name__ == '__main__':
    unittest.main()
