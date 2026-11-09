"""Parser and adapter contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.los_villares import SOURCE, LosVillaresAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def table(title, documents):
    return '<table><tr><th>' + title + '</th><th>Descarga</th></tr>' + ''.join(
        f'<tr><td><a href="{url}">{label}</a></td><td><a href="{url}"><i></i></a></td></tr>'
        for label, url in documents
    ) + '</table>'


def page(body):
    return '<div class="entry-content">' + body + '</div>'


COMMERCIAL = table('INNOVACIÓN DE PLANEAMIENTO / MODIFICACIÓN ART. IX.3.19 NNSS', [
    ('Modificación puntual superficie de venta', '/wp-content/uploads/urbanismo/innovacion/modificacionns.pdf'),
    ('Aprobación definitiva', '/wp-content/uploads/urbanismo/innovacion/bop-modificacionns.pdf'),
])
EQUIPMENT = table('INNOVACIÓN DE PLANEAMIENTO / MODIFICACIÓN NN.SS. EQUIPAMIENTOS SECTOR SUOI2', [
    ('Documento Innovación', '/wp-content/uploads/urbanismo/innovacion2/doc-innovacion.pdf'),
    ('Información pública: Publicación el BOP', '/wp-content/uploads/urbanismo/innovacion2/ip-bop.pdf'),
])
STUDY = table('ESTUDIO DE DETALLE UAS-4 DE CALLE ELICHE – CTRA. DE MARTOS', [
    ('Estudio de Detalle (Documento aprobado inicialmente)', '/wp-content/uploads/urbanismo/planeamiento/estudiodetallecrtmartos.pdf'),
    ('Información Pública: Publicación BOP', '/wp-content/uploads/urbanismo/innovacion/anuncio-aprobacioninicial.pdf'),
    ('Anuncio Aprobación definitiva', '/wp-content/uploads/urbanismo/innovacion/anuncio-aprobaciondefinitiva.pdf'),
])
FORM = table('Modelos', [('Declaración Responsable', '/declaracion-responsable/')])
FIXTURE = page(FORM + COMMERCIAL + EQUIPMENT + STUDY)


class ParserTests(unittest.TestCase):
    def test_groups_instruments_and_retains_all_documents(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 3])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        self.assertIn('innovacion2/ip-bop.pdf', rows[1]['documentos'][1]['url'])
        # The study notices live in another directory: table, not path, owns grouping.
        self.assertIn('innovacion/anuncio-aprobaciondefinitiva.pdf', rows[2]['documentos'][2]['url'])
        self.assertEqual(rows[2]['documentos'][2]['titulo'], 'Anuncio Aprobación definitiva')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '23099')
            self.assertEqual(row['provincia'], 'Jaén')
            self.assertEqual(row['inventory_url'], SOURCE)
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertNotIn(field, row)

    def test_stable_ids_and_duplicate_table_merge(self):
        first = parse_inventory(page(COMMERCIAL))[0]
        merged = parse_inventory(page(COMMERCIAL + COMMERCIAL))[0]
        self.assertEqual(merged, first)
        reversed_rows = parse_inventory(page(STUDY + EQUIPMENT + COMMERCIAL))
        self.assertEqual(first['id'], reversed_rows[2]['id'])

    def test_missing_inventory_and_forms_only_fail(self):
        for html in ('<html>Unavailable</html>', page(''), page(FORM), page('<table><td>Broken</td></table>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_silently_truncating(self):
        for more in ('<a rel="next" href="/page/2/">2</a>',
                     '<a href="?paged=2">2</a>', '<a href="/more/">Siguiente</a>',
                     '<nav class="pagination"><a href="/other/">2</a></nav>'):
            with self.subTest(more=more), self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(page(COMMERCIAL + more))

    def test_changed_sections_and_untrusted_links_fail(self):
        for html in (page(table('Contratación de servicios', [('Anuncio', '/aviso/')])),
                     page(table('Estudio de Detalle UAS-4', [])),
                     FIXTURE.replace('/wp-content/uploads/urbanismo/innovacion2/ip-bop.pdf', 'https://example.org/ip-bop.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)


class AdapterTests(unittest.TestCase):
    def test_manifest_resolves_and_safety_flags(self):
        manifest = load_manifest('los-villares')
        self.assertIsInstance(load_portal_adapter(manifest), LosVillaresAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('23099', 'Los Villares', 'Jaén'))
        self.assertIs(raw['schedule']['enabled'], False)
        self.assertIs(raw['geocode']['jitter_missing'], False)
        self.assertIs(raw['licencias']['enabled'], False)

    @patch('municipio.adapters.los_villares.requests.get')
    def test_refresh_and_failure_preserve_previous_snapshot(self, get):
        get.return_value = Mock(url=SOURCE, text=FIXTURE)
        adapter = LosVillaresAyuntamientoAdapter('los-villares')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(output)['count'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            get.return_value.text = page(STUDY)
            self.assertEqual(adapter.update_proyectos(output, Path(directory)/'state.json')['count'], 1)
            prior = output.read_bytes()
            get.return_value.text = page(FORM)
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(prior, output.read_bytes())
            get.return_value.url = 'https://example.org/'
            with self.assertRaisesRegex(ValueError, 'redirect'):
                adapter.backfill_proyectos(output)
            self.assertEqual(prior, output.read_bytes())

    @patch('municipio.adapters.los_villares.requests.get')
    def test_licences_are_disabled(self, get):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = LosVillaresAyuntamientoAdapter('los-villares').update_licencias(output, output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
