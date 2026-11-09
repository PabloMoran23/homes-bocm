"""Offline parser/adapter checks; fixtures model structure, not live record data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import requests

from municipio.adapters.rafal import SOURCE, RafalAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


FIXTURE = '''<h1>PGOU</h1><nav><a href="/licencias">Solicitud licencia</a></nav>
<div class="elementor-widget-text-editor">
<p><strong>PLANOS DE INFORMACIÓN</strong></p>
<ul><li><a href="/wp-content/uploads/2018/04/plano.pdf">Plano</a></li></ul>
<p><a href="/wp-content/uploads/2018/04/normas.pdf">Normas</a></p>
<p><strong>MODIFICACIÓN PUNTUAL Nº 6 DEL PLAN GENERAL DE RAFAL:</strong></p>
<ul><li><a href="/wp-content/uploads/2024/03/anuncio.pdf">Publicación DOGV anuncio aprobación inicial</a></li>
<li><a href="https://www.modernizaalicante.es/dossierh.14?x=fixture">Certificado anulación acuerdo</a></li></ul>
<p><strong>MODIFICACIÓN PUNTUAL Nº 7 DEL PLAN GENERAL DE RAFAL:</strong></p>
<ul><li><a href="/wp-content/uploads/2026/05/parte1.pdf">1. Modificación</a></li>
<li><a href="/wp-content/uploads/2026/05/parte2.pdf">2. Modificación</a></li>
<li><a href="/wp-content/uploads/2026/05/parte2.pdf">2. Modificación</a></li></ul>
</div>'''


class RafalTests(unittest.TestCase):
    def test_instrument_grouping_provenance_and_deduplication(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2])
        self.assertEqual(rows[-1]['id'], 'rafal-plan-modificacion-7')
        self.assertEqual(rows[0]['documentos'][0]['url'],
                         'https://rafal.es/wp-content/uploads/2018/04/plano.pdf')
        self.assertTrue(all(d['inventory_url'] == SOURCE for r in rows for d in r['documentos']))
        self.assertEqual(rows[1]['advertencias_documentales'], ['Certificado anulación acuerdo'])

    def test_dates_status_and_geometry_are_not_inferred(self):
        for row in parse_inventory(FIXTURE):
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertNotIn('fase', row)
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '03109')

    def test_rejects_navigation_login_and_ambiguous_content(self):
        for html in ('<h1>Login</h1>', '<h1>PGOU</h1><a href="plan.pdf">Plan</a>',
                     FIXTURE + FIXTURE, FIXTURE.replace('Nº 7', 'número siete')):
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_truncating(self):
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<div class="pagination">2</div>'):
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(FIXTURE + extra)
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(FIXTURE.replace('</div>', '<a href="?page=2">Mostrar más</a></div>'))

    def test_changed_document_host_and_empty_group_fail(self):
        with self.assertRaisesRegex(ValueError, 'Unrecognized inventory document'):
            parse_inventory(FIXTURE.replace('/wp-content/uploads/2018/04/plano.pdf', 'https://example.org/plan.pdf'))
        with self.assertRaisesRegex(ValueError, 'without documents'):
            parse_inventory(FIXTURE.replace('</div>', '<strong>MODIFICACIÓN PUNTUAL Nº 8</strong></div>'))

    def test_snapshot_updates_and_http_failure_does_not_overwrite(self):
        response = Mock(url=SOURCE, text=FIXTURE, content=FIXTURE.encode())
        with TemporaryDirectory() as tmp, patch('municipio.adapters.rafal.requests.get', return_value=response):
            output = Path(tmp) / 'proyectos.jsonl'
            adapter = RafalAyuntamientoAdapter('rafal', {'capture_dir': tmp})
            self.assertEqual(adapter.backfill_proyectos(output)['count'], 3)
            before = output.read_bytes()
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / 'state.json')['count'], 3)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            response.raise_for_status.side_effect = requests.HTTPError('403')
            with self.assertRaises(requests.HTTPError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['count'], 0)

    def test_manifest_and_dynamic_registration(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/rafal/manifest.yaml'
        raw = load_yaml(path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('03109', 'Alicante'))
        for section, field in (('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')):
            self.assertIs(raw[section][field], False)
        self.assertIsInstance(load_portal_adapter(load_manifest(path)), RafalAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
