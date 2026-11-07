import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.abrera import AbreraAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return ('<main><div class="element element-rotador"><h2>Urbanisme - documentació '
            'a exposició pública</h2>' + body + '</div></main>')


def link(n, text, extra=''):
    return f'<a href="/files/doc{n}/document.pdf" {extra}>{text}</a>'


class AbreraTests(unittest.TestCase):
    def test_group_documents_and_do_not_infer_dates(self):
        html = page('<p><strong>Projecte <span>parc</span> municipal</strong></p><ul><li>'
                    + link(1, 'Anunci aprovació inicial 2026-02-10') + '</li><li>'
                    + link(2, 'Projecte parc') + '</li><li>'
                    + link(3, 'Anunci aprovació definitiva') + '</li></ul>'
                    '<p>Notícies relacionades 2026-09-09</p>')
        rows, warnings = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['titulo'], 'Projecte parc municipal')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(rows[0][key])
        self.assertEqual(warnings, [])
        self.assertEqual(rows, AbreraAyuntamientoAdapter.parse_projects(html))

    def test_nested_instrument_and_split_heading(self):
        rows, _ = parse_inventory(page('<p><strong>Plànol de delimitació forestal</strong></p><ul><li>'
            + link(1, 'Annex I') + '<strong>Projecte Can Pous</strong></li><li>'
            + link(2, 'Projecte executiu Can Pous') + '</li></ul>'
            '<p><strong>Projecte pícnic </strong><strong>Torrent Gran</strong></p>'
            + link(3, 'Projecte pícnic')))
        self.assertEqual([r['titulo'] for r in rows], ['Plànol de delimitació forestal', 'Projecte Can Pous', 'Projecte pícnic Torrent Gran'])
        self.assertTrue(all(len(r['documentos']) == 1 for r in rows))

    def test_roof_projects_and_conflicting_notice(self):
        rows, warnings = parse_inventory(page('<p>Projectes d’obres per a línies de vida</p>'
            + link(1, 'Projecte coberta Centre Polivalent')
            + link(2, 'Anunci coberta Centre Polivalent')
            + link(3, "Anunci aprovació inicial Escola Ernest Lluch", 'title="Anunci aprovació definitiva"')))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertIsNone(rows[1]['fase'])
        self.assertIn('conflicts', warnings[0]['reason'])

    def test_invalid_links_and_image_duplicates(self):
        rows, warnings = parse_inventory(page('<p>Projecte invàlid</p><a href="bad link">Anunci</a>'
            '<p>Projecte vàlid</p>' + link(1, 'Projecte tècnic') + link(1, '')
            + link(1, 'Projecte tècnic')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(len(warnings), 2)

    def test_reject_empty_login_navigation_and_pagination(self):
        for html in ('<a href="/files/doc1/x.pdf">Projecte</a>', page('<p>Formulari de llicència</p>'),
                     page('<p>Projecte parc</p>' + link(1, 'Projecte')) + '<a rel="next" href="?page=2">Next</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_embedded_documents_keep_provenance_and_deduplicate(self):
        payload = base64.b64encode(b'%PDF-1.7 test fixture').decode()
        image = f'<img src="data:application/pdf;base64,{payload}">'
        rows, _ = parse_inventory(page('<p>Projecte parc</p>' + link(1, 'Projecte') + image + image))
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['url'], SOURCE)
        self.assertEqual(len(rows[0]['documentos'][1]['embedded_sha256']), 64)

    def test_manifest_loading_and_refresh(self):
        manifest = load_manifest('abrera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08001')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        with patch.object(AbreraAyuntamientoAdapter, 'backfill_proyectos', return_value={'rows': 4}) as run:
            adapter = AbreraAyuntamientoAdapter()
            self.assertEqual(adapter.update_proyectos(Path('x'), Path('state')), {'rows': 4})
            run.assert_called_once_with(Path('x'))


if __name__ == '__main__':
    unittest.main()
