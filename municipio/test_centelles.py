"""Offline semantic regression tests; no dependency on local live evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.centelles import CentellesAyuntamientoAdapter as Adapter, BASE
from municipio.manifest import load_manifest


def link(title, name):
    return f'<a href="docs/{name}.pdf">{title}</a>'


def planning(body):
    return '<h2 class="sectionTitle">Planejament urbanístic - Documentació</h2><ul>' + body + '</ul>'


PLAN = planning(
    '<li>' + link('Avanç de Modificació Puntual per ampliació La Gavarra. Febrer 2024', 'avanc') + '</li>'
    '<li>' + link('Document ambiental estratègic La Gavarra. Febrer 2024', 'dae') + '</li>'
    '<li>Modificació puntual número 44 La Gavarra</li><ul><li>' + link('Memòria', 'memoria') + '</li></ul>'
    '<li>Modificación puntual número 44 La Gavarra</li><ul><li>' + link('Memòria', 'castella') + '</li></ul>'
    '<li>Document comprensiu La Gavarra. Aprovació Inicial</li><ul><li>' + link('Document comprensiu', 'resum') + '</li></ul>'
    '<li>' + link('Pla de millora urbana carrer Mare de Déu del Pilar, 3. Abril 2026', 'pmu') + '</li>'
    '<ul><li>' + link("5. Certificat del Ple de l'Ajuntament 20/07/2026. Aprovació provisional del Pla de millora urbana", 'certificat') + '</li>'
    '<li>' + link('Anunci ampliació termini PMU', 'anunci') + '</li></ul>'
    '<li>' + link('Certificat dret de superfície Osonament', 'osonament') + '</li><ul><li>' + link('Memòria justificativa', 'memoria-osonament') + '</li></ul>'
)
WORK = '<h2 class="sectionTitle">Documentació</h2><p>PGO</p><ul><li>' + link('Normes urbanístiques', 'normes') + '</li></ul><p><strong>PROJECTE D\'OBRES</strong></p><ul><li>' + link('Modificació del Projecte tècnic reforma Palau dels Comtes Fase 2', 'palau') + '</li></ul><strong>Projecte executiu Vapor</strong><ul>' + ''.join('<li>' + link(f'Projecte executiu fotovoltaica. Instal·lació {i}', f'vapor{i}') + '</li>' for i in range(1, 5)) + '</ul><h2 class="sectionTitle">Enllaços d’interès</h2><ul><li>' + link('Subvenció', 'subvencio') + '</li></ul>'


class CentellesTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = Adapter.parse_planning(PLAN)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 5)
        self.assertEqual(len(rows[1]['documentos']), 3)
        self.assertEqual(rows[0]['url_documento'], BASE + 'docs/avanc.pdf')
        self.assertNotIn('osonament', json.dumps(rows))
        self.assertTrue(all(d['source_url'] == rows[0]['url'] for d in rows[0]['documentos']))

    def test_date_semantics_and_missing_geometry(self):
        rows = Adapter.parse_planning(PLAN)
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fase'])  # approval document is not an approval
        pmu = rows[1]
        self.assertEqual(pmu['fecha_acuerdo'], '2026-07-20')
        self.assertEqual(pmu['fecha_aprob'], '2026-07-20')
        self.assertEqual(pmu['fase'], 'aprobación provisional')
        self.assertEqual(pmu['fecha_acuerdo_source_url'], BASE + 'docs/certificat.pdf')
        for r in rows:
            for key in ['fecha', 'fecha_publicacion', 'lat', 'lon', 'geometry']:
                self.assertIsNone(r[key])

    def test_works_scope_and_grouping(self):
        rows = Adapter.parse_works(WORK)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]['documentos']), 4)
        self.assertNotIn('normes.pdf', json.dumps(rows))
        self.assertNotIn('subvencio', json.dumps(rows))
        self.assertTrue(all(r['fase'] is None and r['fecha_aprob'] is None for r in rows))

    def test_fail_closed(self):
        for html in ['<p>Login</p>', planning('<li>Llicència d’obres: formulari</li>'), planning('<li>Nova modificació sense identificar</li>')]:
            with self.assertRaises(ValueError):
                Adapter.parse_planning(html)
        with self.assertRaises(ValueError):
            Adapter.parse_planning(PLAN.replace('docs/avanc.pdf', 'https://untrusted.invalid/a.pdf'))
        with self.assertRaises(ValueError):
            Adapter.parse_works('<p>PROJECTE D\'OBRES</p>')

    def test_pagination_rejected(self):
        for pagination in ['<a rel="next" href="?p=2">Next</a>', '<a href="?page=2">2</a>', '<div class="pagination">2</div>']:
            with self.assertRaises(ValueError):
                Adapter.parse_planning(PLAN + pagination)
            with self.assertRaises(ValueError):
                Adapter.parse_works(WORK + pagination)

    def test_snapshot_stability_and_failure_preserves_output(self):
        adapter = Adapter()
        with tempfile.TemporaryDirectory() as directory:
            output, state = Path(directory) / 'rows.jsonl', Path(directory) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=[PLAN, WORK]):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 4)
            original = output.read_text()
            with patch.object(adapter, '_fetch', side_effect=[PLAN, WORK]):
                adapter.update_proyectos(output, state)
            self.assertEqual(output.read_text(), original)
            self.assertFalse(state.exists())
            with patch.object(adapter, '_fetch', side_effect=[PLAN, '<p>Unavailable</p>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('centelles')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertEqual(manifest.portal.config['ine_code'], '08067')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
