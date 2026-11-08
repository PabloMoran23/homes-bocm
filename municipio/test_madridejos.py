import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.madridejos import SOURCE, MadridejosAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def fixture(extra=''):
    labels = ['PORTADA CARPETA', 'MEMORIA INFORMATIVA', 'MEMORIA JUSTIFICATIVA',
              'NORMATIVA MAYO DE 2004', 'O-2 – ZONIFICACIÓN. (ORDENACIÓN)',
              'MODIFICACIÓN PUNTUAL Nº 2 DEL PLAN DE ORDENACIÓN MUNICIPAL DE MADRIDEJOS']
    links = ''.join(f'<li><a href="/docs/{i}.pdf">{label}</a></li>' for i, label in enumerate(labels))
    return ('<a href="/irrelevant.pdf">navigation</a><article><div class="entry-content">'
            '<p>NORMAS URBANÍSTICAS</p><ul>' + links + extra + '</ul></div></article>')


class MadridejosTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [5, 1])
        self.assertEqual(rows[1]['documentos'][0]['url'], 'https://madridejos.es/docs/5.pdf')
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '45087')
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            self.assertNotIn('fase', row)
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))

    def test_no_synthetic_record_from_forms_or_missing_content(self):
        for html in ['', '<article>Solicitud de licencia de obras</article>', fixture().replace('MEMORIA JUSTIFICATIVA', 'SOLICITUD DE LICENCIA')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_not_truncated(self):
        for pagination in ['<a rel="next" href="/2/">2</a>', '<div class="page-links">2</div>', '<a href="?paged=2">2</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(fixture(pagination))

    def test_unknown_instrument_and_external_pdf_fail(self):
        for extra in ['<a href="/new.pdf">PLAN PARCIAL NUEVO</a>', '<a href="https://example.org/a.pdf">MEMORIA INFORMATIVA</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(fixture(extra))

    def test_document_deduplication_and_stable_ids(self):
        duplicate = '<a href="/docs/1.pdf">MEMORIA INFORMATIVA</a>'
        self.assertEqual(parse_inventory(fixture()), parse_inventory(fixture(duplicate)))

    @patch('municipio.adapters.madridejos.requests.get')
    def test_adapter_writes_snapshot_and_preserves_output_on_failure(self, get):
        get.return_value = Mock(url=SOURCE, text=fixture())
        adapter = MadridejosAyuntamientoAdapter('madridejos')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['written'], 2)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            before = out.read_bytes()
            get.return_value.text = ''
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('madridejos')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Madridejos', 'Toledo', '45087'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.madridejos:MadridejosAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
