"""Offline parser and adapter contract tests; fixtures model the reviewed markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.hornachuelos import (
    HornachuelosAyuntamientoAdapter, SOURCES, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def fixture(spec):
    title = 'PLAN GENERAL DE ORDENACIÓN URBANÍSTICA DEL TÉRMINO MUNICIPAL DE HORNACHUELOS (PGOU)'
    docs = ''.join(f'<a href="{spec["prefix"]}{i}.pdf">{label}</a>'
                   for i, label in enumerate(spec['required']))
    return f'<div id="content-main"><h2>{title}</h2>{docs}</div>'


class HornachuelosTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        for spec in SOURCES:
            html = fixture(spec)
            # Duplicate attachment and unrelated navigation must not add records.
            html = html.replace('</div>', f'<a href="{spec["prefix"]}0.pdf">Duplicado</a></div>')
            row = parse_inventory(html + '<a href="/modelo.pdf">Modelo licencia</a>', spec)
            self.assertEqual(len(row['documentos']), 2)
            self.assertEqual(row['codigo_ine'], '14036')
            self.assertTrue(all(d['source_url'] == spec['url'] for d in row['documentos']))
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertNotIn('fase', row)

    def test_reject_missing_content_and_forms(self):
        for html in ('', '<div id="content-main">Modelo de licencias de obras</div>',
                     fixture(SOURCES[0]).replace('NORMATIVA URBANÍSTICA', 'Solicitud')):
            with self.assertRaises(ValueError):
                parse_inventory(html, SOURCES[0])

    def test_pagination_and_foreign_documents_rejected(self):
        spec = SOURCES[0]
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<div class="page-links"><a href="/2">2</a></div>',
                      '<a href="?page=2">Siguiente</a>',
                      '<a href="https://example.org/x.pdf">Normativa</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(fixture(spec).replace('</div>', extra + '</div>'), spec)

    def test_keeps_all_documents_and_encodes_spaces(self):
        spec = SOURCES[0]
        extra = ''.join(f'<a href="{spec["prefix"]}plano {i}.pdf">Plano {i}</a>' for i in range(120))
        row = parse_inventory(fixture(spec).replace('</div>', extra + '</div>'), spec)
        self.assertEqual(len(row['documentos']), 122)
        self.assertIn('plano%20119.pdf', row['documentos'][-1]['url'])

    def test_manifest_and_live_contract(self):
        manifest = load_manifest('hornachuelos')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('14036', 'Córdoba'))
        for section, field in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertFalse(raw[section][field])
        adapter = load_portal_adapter(manifest)
        responses = []
        for spec in SOURCES:
            responses.append(Mock(url=spec['url'], text=fixture(spec), content=fixture(spec).encode()))
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.hornachuelos.requests.get', side_effect=responses):
            path = Path(tmp) / 'projects.jsonl'
            result = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 1)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licenses.jsonl')['rows'], 0)

    def test_failure_does_not_replace_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.hornachuelos.requests.get') as get:
            get.return_value = Mock(url=SOURCES[0]['url'], text='', content=b'')
            path = Path(tmp) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                HornachuelosAyuntamientoAdapter('hornachuelos').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
