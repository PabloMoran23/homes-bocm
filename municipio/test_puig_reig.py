"""Offline parser and failure-atomicity tests; no network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.puig_reig import PuigReigAyuntamientoAdapter
from municipio.entity_policy import classify
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DOC = 'https://www.seu-e.cat/documents/2846680/18506936/plan.pdf/example-id'


def page(items, date='06/06/2025'):
    return f'''<div class="journal-content-article"><ul>{items}</ul>
    <div class="datatable_info_footer paginacio_footer">Actualització: {date} | Font: Propi ens</div></div>'''


class PuigReigTests(unittest.TestCase):
    def parse(self, html):
        return PuigReigAyuntamientoAdapter.parse_inventory(html, 'planejament-urbanistic')

    def test_group_documents_and_separate_page_metadata(self):
        rows = self.parse(page(f'''<li>Modificació POUM entorn camp de futbol<ul>
        <li><a href="{DOC}">Aprovació inicial</a></li>
        <li><a href="{DOC}/annex">Plànols</a></li></ul></li>'''))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['titulo'], 'Modificació POUM entorn camp de futbol')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(row['fecha_actualizacion_fuente'], '2025-06-06')
        for key in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        policy = classify(row)
        self.assertEqual(policy['entity_type'], 'documento')
        self.assertFalse(policy['activity_eligible'])

    def test_category_and_rpuc_are_instruments_not_documents(self):
        rpuc = 'https://dtes.gencat.cat/rpucportal/#/consulta/cercaPublic?codiPublic=2016%2F60771%2FN'
        rows = self.parse(page(f'''<li><a href="{rpuc}">Pla d'ordenació urbanística municipal 2023</a></li>
        <li>Plans parcials<ul><li><a href="{DOC}">Pla parcial del PPU-3</a></li></ul></li>'''))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['titulo'], 'Pla parcial del PPU-3')
        self.assertEqual(rows[0]['url_documento'], rpuc)
        self.assertIsNone(rows[0]['fase'])

    def test_duplicate_instrument_merges_documents_and_keeps_identity(self):
        one = f'<li><a href="{DOC}">Pla parcial del PPU-3</a></li>'
        two = f'<li><a href="{DOC}/annex">Pla parcial del PPU-3</a></li>'
        row = self.parse(page(one + two))[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['id'], self.parse(page(two, '01/01/2026'))[0]['id'])

    def test_pagination_never_silently_truncated(self):
        html = page(f'<li><a href="{DOC}">Pla parcial del PPU-3</a></li>')
        for control in ['<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Següent</a>',
                        '<div class="pagination"><a href="?page=2">2</a></div>']:
            with self.subTest(control=control), self.assertRaisesRegex(ValueError, 'Pagination'):
                self.parse(html + control)

    def test_fail_closed_for_forms_shells_missing_or_external_documents(self):
        samples = ['<h1>Login</h1>', '<a href="/">Urbanisme</a>', page(''),
                   page(f'<li><a href="{DOC}">Sol·licitud de llicència</a></li>'),
                   page('<li>Pla sense document</li>'),
                   page('<li><a href="https://example.org/a.pdf">Pla fals</a></li>')]
        for sample in samples:
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                self.parse(sample)

    def test_failed_fetch_does_not_replace_existing_snapshot(self):
        adapter = PuigReigAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            out.write_text('previous complete snapshot\n')
            with patch('municipio.adapters.puig_reig.requests.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous complete snapshot\n')

    def test_manifest_loads_adapter_and_disables_licences(self):
        manifest = load_manifest('puig-reig')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, PuigReigAyuntamientoAdapter)
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
