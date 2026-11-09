"""Offline parser/adapter checks; fixture identifiers are test data, not output."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.porqueres import SOURCE, PorqueresAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


VALIDATOR = 'https://porqueres.emunicipis.ddgi.cat/OAC/ValidarDoc.jsp?idioma=ca'
CSV1 = '11111111-1111-4111-8111-111111111111'
CSV2 = '22222222-2222-4222-8222-222222222222'
CSV3 = '33333333-3333-4333-8333-333333333333'


def entry(exp, title, codes=(CSV1,), phase='aprovació inicial'):
    return (f'<p><strong>Expedient: {exp} – {title}</strong></p>'
            f'<p>Exposició al públic <strong>{phase}</strong></p>'
            f'<a href="{VALIDATOR}">aquí</a><ul>' +
            ''.join(f'<li>CSV Document {i}: {code}</li>' for i, code in enumerate(codes)) + '</ul>')


def page(body):
    return ('<article><h1>Documents i projectes en fase d’exposició pública</h1>'
            f'<div class="entry-content">{body}</div></article>')


class PorqueresTests(unittest.TestCase):
    def test_nested_sections_group_documents_and_exclude_nonworks(self):
        html = page(
            entry('X2026000001', 'PROJECTE DE MILLORA DEL PAVELLÓ', (CSV1, CSV2)) +
            '<div><hr><div>' + entry('X2026000002', 'PROJECTE DE VORERA', (CSV3,), 'aprovació definitiva') +
            '</div><hr>' + entry('X2026000003', 'PLA D’IGUALTAT') + '<hr>' +
            entry('X2026000004', 'LLICÈNCIA AMBIENTAL DEIXALLERIA MUNICIPAL') + '<hr>' +
            entry('X2026000005', 'ANUNCI DE LICITACIÓ PROJECTE PAVELLÓ') + '<hr>' +
            entry('X2026000006', 'SOL·LICITUD DE LLICÈNCIA D’OBRES') + '</div>')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([d['csv'] for d in rows[0]['documentos']], [CSV1, CSV2])
        self.assertEqual([d['csv'] for d in rows[1]['documentos']], [CSV3])
        self.assertEqual(rows[1]['fase'], 'aprobación definitiva')
        self.assertEqual(rows[0]['documentos'][0]['url'], VALIDATOR)
        self.assertEqual(rows[0]['documentos'][0]['access'], 'manual_csv_validation')

    def test_versions_merge_by_expediente(self):
        rows = parse_inventory(page(entry('X2026000001', 'PROJECTE DE VORERA') + '<hr>' +
                                    entry('X2026000001', 'PROJECTE DE VORERA', (CSV2,))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_document_month_and_expediente_year_are_not_approval_dates(self):
        row = parse_inventory(page(entry('X2026000001', 'PROJECTE DE VORERA – Novembre 2025',
                                         phase='Aprovació de la memòria')))[0]
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_rejects_pagination_missing_documents_and_changed_structure(self):
        valid = entry('X2026000001', 'PROJECTE DE VORERA')
        for html in (page(valid + '<a rel="next" href="?page=2">2</a>'),
                     page(valid + '<div class="pagination">2</div>'),
                     page(valid + '<a href="?page=2">Següent</a>'),
                     page(valid.replace(CSV1, 'missing')),
                     page(valid.replace(VALIDATOR, 'https://example.org/doc')),
                     page(valid + entry('X2026000002', 'PROJECTE DE CAMÍ')),
                     page('<p>X2026000001 PROJECTE DE CAMÍ</p>'),
                     page('No records'), '<html>Access denied</html>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_refresh_and_failure_preserves_previous_output(self):
        response = Mock(url=SOURCE, text=page(entry('X2026000001', 'PROJECTE DE VORERA')))
        adapter = PorqueresAyuntamientoAdapter()
        with TemporaryDirectory() as tmp, patch('municipio.adapters.porqueres.requests.get', return_value=response):
            output = Path(tmp) / 'proyectos.jsonl'
            adapter.backfill_proyectos(output)
            first = output.read_text()
            self.assertEqual(json.loads(first)['expediente'], 'X2026000001')
            adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), first)
            response.text = '<html>Unavailable</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), first)
            disabled = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(disabled)['status'], 'disabled')
            self.assertEqual(disabled.read_text(), '')

    def test_manifest_identity_and_safety_flags(self):
        manifest = load_manifest('porqueres')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('17137', 'Porqueres', 'Girona'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
