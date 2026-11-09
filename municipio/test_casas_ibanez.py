"""Offline parser and adapter failure-contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.casas_ibanez import (
    BASE, INSTANCIAS, MAP_LABEL, NORMATIVA, PLAN_LABEL,
    CasasIbanezAyuntamientoAdapter, parse_projects,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


NORMS = f'''<main><h1>Normativa Municipal</h1><ul>
<li><strong>Aprobación definitiva de modificación de tasa del Cementerio</strong>
<ul><li><a href="https://www.dipualba.es/tasa.pdf">BOP 24/11/2023</a></li></ul></li>
<li><strong>{PLAN_LABEL}</strong><ul><li>
<a href="http://casasibanez.es/wp-content/uploads/2024/02/normas.pdf">NNUU JUN 2021</a>
</li></ul></li></ul></main>'''
FORMS = f'''<main><h1>Instancias</h1>
<a href="/wp-content/uploads/2026/01/licencia.docx">Solicitud de licencia de obra mayor</a>
<a href="/wp-content/uploads/2026/01/declaracion.pdf">Declaración responsable de obra menor</a>
<a href="/wp-content/uploads/2026/01/plano.pdf">{MAP_LABEL}</a></main>'''


class ParserTests(unittest.TestCase):
    def test_grouped_instrument_and_date_semantics(self):
        rows = parse_projects(NORMS, FORMS)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['codigo_ine'], row['provincia']), ('02024', 'Albacete'))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual({d['inventory_url'] for d in row['documentos']}, {NORMATIVA, INSTANCIAS})
        self.assertTrue(row['documentos'][0]['url'].startswith('https://'))
        self.assertTrue(row['documentos'][0]['url_enlace_original'].startswith('http://'))
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field], field)
        self.assertFalse(row['publication_ready'])
        self.assertNotIn('licencia.docx', json.dumps(row))
        self.assertNotIn('tasa.pdf', json.dumps(row))

    def test_all_group_documents_retained_and_deduplicated(self):
        extra = '<a href="/wp-content/uploads/2024/02/anexo.pdf">Anexo POM</a>'
        html = NORMS.replace('NNUU JUN 2021</a>', 'NNUU JUN 2021</a>' + extra + extra)
        self.assertEqual(len(parse_projects(html, FORMS)[0]['documentos']), 3)

    def test_stable_identity_after_document_relocation(self):
        self.assertEqual(parse_projects(NORMS, FORMS)[0]['id'],
                         parse_projects(NORMS.replace('normas.pdf', 'normas-nuevo.pdf'), FORMS)[0]['id'])

    def test_forms_navigation_and_login_are_not_records(self):
        for html in ['<main><h1>Iniciar sesión</h1></main>',
                     '<main><h1>Normativa Municipal</h1><a href="/pom">Plan de Ordenación Municipal</a></main>',
                     NORMS.replace(PLAN_LABEL, 'Solicitud de licencia de obras')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html, FORMS)

    def test_missing_documents_or_ambiguous_group_fail(self):
        for html, forms in [(NORMS.replace('href=', 'data-href='), FORMS),
                            (NORMS, FORMS.replace(MAP_LABEL, 'Otro plano')),
                            (NORMS.replace('</ul></main>', f'<li><strong>{PLAN_LABEL}</strong></li></ul></main>'), FORMS)]:
            with self.subTest(html=html, forms=forms), self.assertRaises(ValueError):
                parse_projects(html, forms)

    def test_unverified_document_hosts_and_types_fail(self):
        for target in ['https://example.org/normas.pdf',
                       'https://casasibanez.es.evil.org/wp-content/uploads/normas.pdf',
                       BASE + '/wp-content/uploads/licencia.docx', 'javascript:alert(1)']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                parse_projects(NORMS.replace('http://casasibanez.es/wp-content/uploads/2024/02/normas.pdf', target), FORMS)

    def test_pagination_cannot_be_silently_truncated(self):
        for pagination in ['<nav class="pagination">2</nav>', '<a rel="next" href="?page=2">2</a>',
                           '<div class="page-links">2</div>']:
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_projects(NORMS, FORMS.replace('</main>', pagination + '</main>'))


class AdapterTests(unittest.TestCase):
    def test_manifest_loads_and_registry_resolves(self):
        manifest = load_manifest('casas-ibanez')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '02024')
        self.assertEqual(manifest.provincia, 'Albacete')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CasasIbanezAyuntamientoAdapter)

    def test_live_snapshot_contract_and_failed_fetch_preserves_output(self):
        adapter = CasasIbanezAyuntamientoAdapter('casas-ibanez')
        def fetch(url, **kwargs):
            return {NORMATIVA: NORMS.encode(), INSTANCIAS: FORMS.encode()}.get(url, b'%PDF-1.7 test')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            state = Path(tmp) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=fetch):
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(result['source_urls']), 4)
            snapshot = output.read_bytes()
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertFalse(state.exists())
            with patch.object(adapter, '_fetch', side_effect=RuntimeError('source unavailable')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), snapshot)

    def test_disabled_licences_do_not_fetch_forms(self):
        adapter = CasasIbanezAyuntamientoAdapter('casas-ibanez')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch') as fetch:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.update_licencias(output, Path(tmp) / 'state.json')['status'], 'disabled')
            self.assertEqual(output.read_text(), '')
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
