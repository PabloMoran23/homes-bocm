import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.calasparra import API, SOURCE, CalasparraAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def document(title, name):
    return f'<a href="/wp-content/uploads/2020/05/{name}.pdf">{title}</a>'


def page(extra=''):
    return {'slug': 'urbanisme', 'status': 'publish', 'link': SOURCE,
            'date': '2020-06-15T17:55:01', 'modified': '2026-01-01T00:00:00',
            'content': {'rendered': '<h3>RÈGLES SUBSIDIAIRES</h3>' +
                '<div class="accordion-content">' + document('CALASPARRA 1', 'calas-1') + '</div>' +
                '<div class="accordion-content">' + document('PLANO 1', 'map-1') + '</div>' +
                '<div class="accordion-content">' +
                document('DELIMITACIÓN NÚCLEO VALENTÍN', 'valentin') +
                document('DELIMITACIÓN NÚCLEO VALENTÍN – APTO PARA URBANIZAR', 'valentin-apto') +
                document('DELIMITACIÓN NÚCLEO LA ÑORA', 'nora') +
                document('PLAN PARCIAL RIÑALES _FASE III', 'rinales-iii') +
                document('RIÑALES FASE III PARCELAS Model (1)', 'rinales-map') +
                document('PLAN PARCIAL RIÑALES-FASE II', 'rinales-ii') +
                document('LOS RIÑALES-PARCELARIO FASES I – II', 'parcels') +
                document('P P – CAÑADA MANRIQUE FASE II', 'canada-plan') +
                document('PARCELARIO CAÑADA MANRIQUE FASE II', 'canada-parcels') +
                extra + '</div>'}}


class CalasparraTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        rows, omitted = parse_inventory(page())
        self.assertEqual(len(rows), 6)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1, 2, 1, 2])
        self.assertEqual(len(omitted), 1)
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '30013')
            self.assertEqual(row['inventory_url'], SOURCE)
            self.assertEqual(row['source_api_url'], API)
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)
        self.assertIn('calas-1.pdf', rows[0]['documentos'][0]['url'])
        self.assertIn('rinales-ii.pdf', rows[4]['documentos'][0]['url'])

    def test_ids_stable_with_document_changes(self):
        before, _ = parse_inventory(page())
        after, _ = parse_inventory(page(document('DELIMITACIÓN NÚCLEO LA ÑORA', 'nora-extra')))
        self.assertEqual([r['id'] for r in before], [r['id'] for r in after])

    def test_fail_closed_on_source_changes(self):
        for extra in (document('Instancia licencia', 'licencia'),
                      '<a href="https://example.org/plan.pdf">PLAN PARCIAL RIÑALES-FASE II</a>',
                      '<a rel="next" href="?page=2">Siguiente</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(page(extra))
        for value in ({}, {**page(), 'status': 'draft'},
                      {**page(), 'content': {'rendered': '<h3>Nothing</h3>'}}):
            with self.assertRaises(ValueError):
                parse_inventory(value)

    @patch('municipio.adapters.calasparra.requests.get')
    def test_live_transport_pagination_and_no_partial_overwrite(self, get):
        adapter = CalasparraAyuntamientoAdapter('calasparra')
        response = Mock(url=API, headers={'X-WP-Total': '1', 'X-WP-TotalPages': '1'})
        response.json.return_value = [page()]
        get.return_value = response
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['count'], 6)
            original = out.read_text()
            response.headers['X-WP-TotalPages'] = '2'
            with self.assertRaises(ValueError):
                adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), original)
            self.assertEqual(len([json.loads(line) for line in original.splitlines()]), 6)

    def test_manifest_loads_real_adapter(self):
        manifest = load_manifest('calasparra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CalasparraAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
