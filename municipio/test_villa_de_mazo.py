import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villa_de_mazo import (
    MUNICIPAL_URL, VillaDeMazoAyuntamientoAdapter, discover_dossier, parse_dossier,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

DOSSIER = 'https://www.gobiernodecanarias.org/planificacionterritorial/materias/exposicion-de-planes-y-normas/mazo/'
DOC = 'https://www.gobiernodecanarias.org/planificacionterritorial/descargas/mazo/'
MUNICIPAL = f'<a href="{DOSSIER}">Plan General de Ordenación</a>'
HTML = f'''<div id="centercontainer"><h2 class="titulo-modernizacion">Aprobación de correcciones y nueva información pública del Plan General de Ordenación de la Villa de Mazo.</h2>
<div class="texto-rico-basico"><a href="{DOC}resolucion.pdf">Acuerdo de fecha 24 de julio de 2026</a>
<a href="{DOC}indice.pdf">Índice</a><a href="{DOC}plan.zip">Documento PGO</a>
<a href="{DOC}indice.pdf">Duplicado</a></div></div>
<footer><a href="{DOC}unrelated.pdf">Otro documento</a></footer>'''


class VillaDeMazoTests(unittest.TestCase):
    def test_discovery_and_duplicate_menu_links(self):
        self.assertEqual(discover_dossier(MUNICIPAL * 2), DOSSIER)
        for html in ('<p>Licencias de obra mayor</p>', MUNICIPAL.replace('www.gobiernodecanarias.org', 'example.org'),
                     MUNICIPAL + MUNICIPAL.replace('/mazo/', '/other/')):
            with self.assertRaises(ValueError):
                discover_dossier(html)

    def test_grouping_and_semantics(self):
        rows = parse_dossier(HTML, DOSSIER)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['codigo_ine'], '38053')
        self.assertIn('24 de julio de 2026', row['documentos'][0]['titulo'])
        self.assertFalse(row['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)

    def test_fail_closed_when_missing_or_changed(self):
        for html in ('<html>Service unavailable</html>', HTML.replace('Villa de Mazo', 'Otro Municipio'),
                     HTML.replace('plan.zip', 'plan.txt'), HTML.replace(DOC, 'https://example.org/')):
            with self.assertRaises(ValueError):
                parse_dossier(html, DOSSIER)

    def test_pagination_not_silently_ignored(self):
        for pagination in ('<a href="?page=2" rel="next">2</a>', '<a href="?page=2">Siguiente</a>',
                           '<div class="pagination"><a href="?page=2">2</a></div>'):
            with self.assertRaises(ValueError):
                parse_dossier(HTML.replace('<div id="centercontainer">', '<div id="centercontainer">' + pagination), DOSSIER)

    def test_manifest_and_real_adapter_contract(self):
        manifest = load_manifest('villa-de-mazo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '38053')
        self.assertEqual(manifest.provincia, 'Santa Cruz de Tenerife')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'proyectos.jsonl'
            with patch.object(VillaDeMazoAyuntamientoAdapter, '_fetch', side_effect=[MUNICIPAL, HTML]):
                result = adapter.update_proyectos(output, Path(d) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(output.read_text())['titulo'], parse_dossier(HTML, DOSSIER)[0]['titulo'])
            with patch.object(VillaDeMazoAyuntamientoAdapter, '_fetch', side_effect=[MUNICIPAL, '<html>Error</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            with patch('requests.get', side_effect=AssertionError('Licences must not fetch')):
                self.assertTrue(adapter.backfill_licencias(Path(d) / 'licencias.jsonl')['disabled'])


if __name__ == '__main__':
    unittest.main()
