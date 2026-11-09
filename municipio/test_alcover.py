import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alcover import AlcoverAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest


def fixture(extra='', label='APROVACIÓ PROVISIONAL', doc=True):
    return f'''<div class="journal-content-article">
    <div class="md-htmlblock">
    <p>PLA D'ORDENACIÓ URBANÍSTICA MUNICIPAL</p>
    <a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/259791/documents">POUM</a>
    <p>MODIFICACIÓ PUNTUAL NÚM. 17 DEL POUM</p>
    <p>Regulació de la parcel·la mínima. {label}</p>
    {('<a href="/documents/6990119/17/plan.pdf/id">Pla</a>' if doc else '')}
    {extra}</div><p>Actualització: 02/11/2026</p>
    <h2>PLANS ESPECIALS URBANÍSTICS</h2>
    <a href="/documents/6990119/other/special.pdf/id">Other instrument</a></div>'''


class AlcoverTests(unittest.TestCase):
    def test_grouping_and_section_boundary(self):
        rows = AlcoverAyuntamientoAdapter.parse_projects(fixture(
            '<a href="/documents/6990119/17/annex.pdf/id">Annex</a>'
            '<a href="/documents/6990119/17/plan.pdf/id">Duplicate</a>'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertTrue(rows[1]['url_documento'].startswith('https://seu-e.cat/documents/'))
        self.assertNotIn('Actualització', rows[1]['descripcion'])
        self.assertNotIn('PLANS ESPECIALS', rows[1]['descripcion'])
        self.assertEqual(rows[1]['fase'], 'aprobación provisional')
        for row in rows:
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertEqual(row['codigo_ine'], '43005')
            self.assertFalse(row['publication_ready'])

    def test_stages_not_inferred_from_dossier(self):
        rows = AlcoverAyuntamientoAdapter.parse_projects(fixture(label=''))
        self.assertIsNone(rows[0]['fase'])
        self.assertIsNone(rows[1]['fase'])
        self.assertEqual(AlcoverAyuntamientoAdapter.parse_projects(
            fixture(label='Document aprovat inicialment'))[1]['fase'], 'aprobación inicial')

    def test_identity_independent_of_document_order(self):
        a = AlcoverAyuntamientoAdapter.parse_projects(fixture())[1]['id']
        b = AlcoverAyuntamientoAdapter.parse_projects(fixture(label=''))[1]['id']
        self.assertEqual(a, b)

    def test_no_navigation_or_licence_forms(self):
        for html in ('<a href="/documents/form.pdf">Sol·licitud llicència</a>', '<p>Login</p>'):
            with self.assertRaises(ValueError):
                AlcoverAyuntamientoAdapter.parse_projects(html)

    def test_missing_or_untrusted_document_fails(self):
        for extra in ('', '<a href="https://untrusted.example/documents/file.pdf">Pla</a>'):
            with self.assertRaises(ValueError):
                AlcoverAyuntamientoAdapter.parse_projects(fixture(doc=False, extra=extra))

    def test_duplicate_heading_and_pagination_fail(self):
        for extra in ('<p>MODIFICACIÓ PUNTUAL NÚM. 17 DEL POUM</p>',
                      '<a rel="next" href="?page=2">Next</a>'):
            with self.assertRaises(ValueError):
                AlcoverAyuntamientoAdapter.parse_projects(fixture(extra))

    def test_snapshot_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            adapter = AlcoverAyuntamientoAdapter('alcover')
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def raise_for_status(self): pass
                def iter_content(self, size): yield fixture().encode()
            with patch('municipio.adapters.alcover.requests.get', return_value=Response()) as get:
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
                self.assertEqual(result['rows'], 2)
                self.assertEqual(len([json.loads(s) for s in out.read_text().splitlines()]), 2)
                self.assertEqual(get.call_args.args[0], SOURCE)
            previous = out.read_bytes()
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_bytes(), previous)

    def test_manifest(self):
        manifest = load_manifest('alcover')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.config['ine_code'], '43005')


if __name__ == '__main__':
    unittest.main()
