"""Offline contract tests; no network or local evidence required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.riells_i_viabrea import RiellsIViabreaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def doc(number, title="Projecte", host=""):
    return (f'<li><a href="{host}/documents/663872/13265083/file/'
            f'00000000-0000-0000-0000-{number:012d}">{title}</a></li>')


def inventory(body):
    return ('<div class="journal-content-article"><div>'
            '<h3>Projectes en exposició pública</h3>' + body + '</div></div>')


def title(text):
    return f'<ul><li><strong>{text}</strong></li></ul>'


class RiellsIViabreaTests(unittest.TestCase):
    def test_groups_project_addendum_and_deduplicates_host_alias(self):
        rows = Adapter.parse_projects(inventory(
            title('Pojecte executiu SAIAR') + '<p>Adaptació del pavelló.</p><ul>'
            + doc(1) + doc(1, host='https://www.seu-e.cat') + doc(2, 'Addenda') + '</ul>'
            + title('Pavimentació de la Plaça del Mercat') + '<ul>' + doc(3) + doc(4, 'Plànol') + '</ul>'
        ))
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(rows[0]['descripcion'], 'Adaptació del pavelló.')
        renamed = inventory(title('Projecte SAIAR revisat') + '<ul>' + doc(1) + '</ul>')
        self.assertEqual(rows[0]['id'], Adapter.parse_projects(renamed)[0]['id'])

    def test_reparcelling_paragraph_boundaries_and_section_mismatch(self):
        rows = Adapter.parse_projects(inventory(
            '<h3>Projectes de reparcel·lació</h3>'
            '<p>Aprovar inicialment el projecte de reparcel·lació PAa-2 Plemen.</p><ul>' + doc(1) + '</ul>'
            '<p>Modificació i refosa del projecte de reparcel·lació Pla del Mercat (JUNY 2025)</p><ul>'
            + doc(2) + doc(3, 'Plànols') + '</ul>'
            "<h3>Projectes d'urbanització</h3><p>Aprovat inicialment el projecte PAa-2</p>"
            + title('Projecte de Reparcel·lació PAa-3 Plemen') + '<ul>'
            + doc(4, 'Acord Aprovació inicial') + doc(5, 'Memòria') + '</ul>'
        ))
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['tipo'] for r in rows], ['reparcelacion'] * 3)
        self.assertEqual(rows[2]['seccion_fuente'], "Projectes d'urbanització")
        self.assertEqual(rows[2]['fase'], 'aprobación inicial')

    def test_dates_do_not_leak_from_parent_plan_or_partial_date(self):
        row = Adapter.parse_projects(inventory(
            title('Modificació puntual del Poum. Aprovació inicial novembre 2025.')
            + '<p>El POUM va ser aprovat el 22 de juliol de 2014 i publicat el 2 d’octubre de 2014.</p>'
            + '<ul>' + doc(1) + '</ul><div>Actualització: 22/09/2026</div>'
        ))[0]
        self.assertEqual(row['fase'], 'aprobación inicial')
        for key in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_groups_reviewed_plemen_alias_preserving_both_labels(self):
        html = inventory(
            '<h3>Projectes de reparcel·lació</h3>'
            '<p>Aprovar inicialment el projecte de reparcel·lació PAa-2 Sector Plemen</p><ul>'
            + doc(1).replace('00000000-0000-0000-0000-000000000001', '33abae7d-fda3-4af6-b9c3-b4fb0495a269')
            + '</ul>' + "<h3>Projectes d'urbanització</h3>"
            + title('Projecte de Reparcel·lació PAa-3 Sector Plemen') + '<ul>'
            + doc(2, 'Acord Aprovació inicial').replace('00000000-0000-0000-0000-000000000002', '3fd9dc10-1147-4b75-9ef0-6a665b2f34ca')
            + doc(3, 'Memòria') + '</ul>'
        )
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(len(rows[0]['titulos_fuente']), 2)
        self.assertIn('PAa-3', rows[0]['titulo'])
        self.assertIn('conflicts', rows[0]['nota_fuente'])

    def test_excludes_unrelated_and_hidden_entries(self):
        body = title('Projecte Pinetell') + '<ul>' + doc(1) + '</ul>'
        for excluded in ['Ordenança reguladora', 'Suspensió potestativa de llicències i instruments',
                         'Modificació del Reglament del Servei', 'Memòria del servei', 'Informe tècnic']:
            body += title(excluded) + '<ul>' + doc(2) + '</ul>'
        body += '<!--' + title('Projecte retirat') + '<ul>' + doc(3) + '</ul>-->'
        self.assertEqual(len(Adapter.parse_projects(inventory(body))), 1)

    def test_fail_closed_for_navigation_empty_pagination_and_foreign_documents(self):
        valid = title('Projecte Pinetell') + '<ul>' + doc(1) + '</ul>'
        invalid = [
            '<a href="/projects">Projectes</a>', inventory(title('Projecte sense document')),
            inventory(valid) + '<a rel="next" href="?page=2">2</a>',
            inventory(valid) + '<a href="?page=2">Següent</a>',
            inventory(title('Projecte') + '<ul>' + doc(1, host='https://example.org') + '</ul>'),
        ]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_resolves_and_disabled_licences(self):
        manifest = load_manifest('riells-i-viabrea')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']),
                         ('Riells i Viabrea', 'Girona', '17146'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_update_refreshes_snapshot_and_rejects_corrupt_response_without_overwrite(self):
        adapter = Adapter('riells-i-viabrea')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            adapter._write(path, [{'id': 'previous'}])
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state.json'), {'rows': 2})
                backfill.assert_called_once_with(path)
            with patch('municipio.adapters.riells_i_viabrea.requests.get') as get:
                response = get.return_value.__enter__.return_value
                response.url = 'https://seu-e.cat/ca/web/riellsiviabrea'
                response.iter_content.return_value = [b'<html>Login</html>']
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(json.loads(path.read_text()), {'id': 'previous'})


if __name__ == '__main__':
    unittest.main()
