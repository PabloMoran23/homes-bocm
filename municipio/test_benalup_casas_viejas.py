"""Offline semantic/parser regression tests, with representative Phoca markup."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.benalup_casas_viejas import (
    HOME, BenalupCasasViejasAyuntamientoAdapter, discover_inventory,
    make_records, parse_catalog,
)
from municipio.manifest import load_manifest

CATALOG = HOME + 'ayuntamiento/avance-pbom'
HOME_HTML = '''<a href="/images/documentos/PGOU%20VIGENTE.pdf">PGOU vigente</a>
<a href="/es/ayuntamiento/avance-pbom">AVANCE PBOM</a>
<a href="/images/documentos/PGOU%20VIGENTE.pdf">PGOU vigente</a>
<a href="/news">Noticias</a>'''


def catalog(extra='', limit=20):
    return f'''<div id="phoca-dl-category-box"><h3 class="pd-ctitle">PBOM</h3>
<div class="pd-filename"><a href="?download=4:documento-urbanistico">Documento urbanístico</a></div>
<div class="pd-filename"><a href="?download=5:documento-inicial-estrategico">Documento inicial estratégico</a></div>
<a href="/licencia">Solicitud de licencia</a>
<a title="Date: 30 Enero 2026">Details</a>
<select name="limit"><option value="{limit}" selected>Limit</option></select>{extra}</div>'''


class ParserTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        inventory = discover_inventory(HOME_HTML)
        docs, pages = parse_catalog(catalog(), CATALOG)
        rows = make_records(inventory, docs)
        self.assertEqual(pages, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2])
        self.assertEqual(rows[1]['fase'], 'avance')
        self.assertNotIn('fase', rows[0])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '11901')
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])
        self.assertEqual(docs[0]['inventory_url'], CATALOG)
        self.assertNotIn('Solicitud', json.dumps(rows))

    def test_pagination_is_exposed(self):
        _, pages = parse_catalog(catalog('<div class="pagination"><a href="?start=20">Next</a></div>', 2), CATALOG)
        self.assertEqual(pages, [CATALOG + '?start=20'])
        with self.assertRaisesRegex(ValueError, 'Full PBOM page'):
            parse_catalog(catalog(limit=2), CATALOG)

    def test_empty_and_wrong_category_rejected(self):
        for html in ('', '<h3>PBOM</h3>', catalog().replace('>PBOM<', '>Ordenanzas<')):
            with self.assertRaises(ValueError):
                parse_catalog(html, CATALOG)
        with self.assertRaises(ValueError):
            parse_catalog('<div id="phoca-dl-category-box"><h3 class="pd-ctitle">PBOM</h3></div>', CATALOG)

    def test_official_links_required(self):
        with self.assertRaises(ValueError):
            discover_inventory(HOME_HTML.replace('/images/documentos/', 'https://example.org/'))
        with self.assertRaises(ValueError):
            parse_catalog(catalog().replace('?download=4:', 'https://example.org/?download=4:'), CATALOG)
        with self.assertRaises(ValueError):
            parse_catalog(catalog('<div class="pagination"><a href="https://example.org/">Next</a></div>'), CATALOG)
        with self.assertRaises(ValueError):
            discover_inventory('<a href="/licencias">Licencias</a>')

    def test_live_traversal_mock_and_disabled_licences(self):
        adapter = BenalupCasasViejasAyuntamientoAdapter('benalup-casas-viejas')
        page2 = catalog().replace('download=5:', 'download=6:')
        class Response:
            url = HOME
            status_code = 200
            headers = {'Content-Type': 'application/pdf'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): return iter([b'%PDF-1.7'])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'projects.jsonl'
            with patch.object(adapter, '_html', side_effect=[HOME_HTML, catalog('<div class="pagination"><a href="?start=20">Next</a></div>'), page2]), patch('requests.Session.get', return_value=Response()):
                result = adapter.backfill_proyectos(output)
            self.assertEqual(result['catalog_pages'], 2)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows[1]['documentos']), 3)
            result = adapter.backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')

    def test_form_in_document_slot_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unrecognized PBOM attachment'):
            parse_catalog(catalog().replace('>Documento urbanístico<', '>Solicitud de licencia<'), CATALOG)

    def test_manifest(self):
        manifest = load_manifest('benalup-casas-viejas')
        self.assertEqual(manifest.provincia, 'Cádiz')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
