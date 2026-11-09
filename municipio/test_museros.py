import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.museros import MuserosAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def doc(title, name):
    return f'<a href="/wp-content/uploads/2026/10/{name}.pdf">{title}</a>'


MOD = '<h3>MODIFICACIÓN PUNTUAL DE LAS NORMAS SUBSIDIARIAS DE PLANEAMIENTO</h3><h6>Creación de las subzonas CASCO-NHT y CASCO-GEN</h6>' + doc('BORRADOR MODIFICACIÓN PUNTUAL Nº 9', 'draft') + doc('MODIFICACIÓN PUNTUAL Nº 9', 'die')
CONSOLIDATED = '<h3>TEXTO CONSOLIDADO DE PLANEAMIENTO URBANÍSTICO DE MUSEROS</h3>' + doc('TEXTO CONSOLIDADO NORMAS URBANÍSTICAS', 'norms') + doc('MAPA OP 4.1 UNIDADES DE EJECUCIÓN', 'map')


def page(body):
    return '<nav>' + doc('Solicitud licencia', 'form') + '</nav><article><div class="entry-content">' + body + '</div></article>'


class MuserosTests(unittest.TestCase):
    def test_grouping_provenance_and_no_inferred_metadata(self):
        rows = parse_inventory(page(MOD + CONSOLIDATED))
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertIn('nº 9', rows[0]['titulo'])
        self.assertIn('CASCO-NHT', rows[0]['descripcion'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '46177')
            self.assertFalse(row['publication_ready'])
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[field])
            self.assertTrue(all(d['source_url'] == row['url'] for d in row['documentos']))
        self.assertNotIn('form.pdf', str(rows))

    def test_stable_ids_document_dedup_and_order_independence(self):
        original = parse_inventory(page(MOD + CONSOLIDATED))
        updated = parse_inventory(page(CONSOLIDATED + MOD + doc('MODIFICACIÓN PUNTUAL Nº 9', 'die')))
        self.assertEqual({r['id'] for r in original}, {r['id'] for r in updated})
        self.assertEqual(len(updated[1]['documentos']), 2)

    def test_fail_closed_on_changed_inventory(self):
        cases = ['', page(''), page(doc('Solicitud', 'form')), page('<h3>Contratos</h3>' + doc('Anuncio', 'tender')),
                 page(MOD.replace('Nº 9', 'Nº 8', 1)), page(CONSOLIDATED.replace('TEXTO CONSOLIDADO NORMAS URBANÍSTICAS', 'ÍNDICE')),
                 page(MOD.replace('/wp-content/uploads/', 'https://example.org/')), page(MOD + MOD)]
        for html in cases:
            with self.subTest(html=html[:90]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_explicit_error(self):
        for nav in ['<a rel="next" href="?page=2">Next</a>', '<div class="page-links">2</div>', '<a href="?paged=2">2</a>']:
            with self.subTest(nav=nav), self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(page(MOD + nav))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('museros')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46177')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), MuserosAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.museros.requests.get') as get:
            out = Path(tmp) / 'licencias.jsonl'
            result = MuserosAyuntamientoAdapter('museros').update_licencias(out, Path(tmp) / 'state')
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
