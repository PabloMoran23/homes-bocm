import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.llagostera import LlagosteraAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def doc(label, name, folder='123'):
    return f'<li><a href="https://seu-e.cat/documents/27933/{folder}/{name}.pdf/uuid-{name}">{label}</a></li>'


def section(title="Aprovació del projecte de reforma (exp. 2026/12)", final=True, dated=True):
    text = f'<p><strong>{title}</strong></p><ul>'
    text += doc("Certificat de la Junta de Govern Local de data 22 d'octubre de 2026, d'aprovació inicial", 'initial')
    text += doc('Projecte aprovació inicial', 'project')
    if final:
        label = "Certificat de decret d'alcaldia d'aprovació definitiva"
        if dated:
            label = "Certificat de la Junta de Govern Local de data 3 de novembre de 2026, d'aprovació definitiva"
        text += doc(label, 'final')
        text += doc('Projecte aprovació definitiva', 'project-final')
    return text + '</ul>'


def page(content):
    return '<div class="journal-content-article">' + content + '<div>Actualització: 06/11/2026</div></div>'


class LlagosteraTests(unittest.TestCase):
    def test_group_versions_and_date_semantics(self):
        rows = Adapter.parse_projects(page(section()))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['fecha_acuerdo'], '2026-11-03')
        self.assertEqual(row['eventos'][0]['fecha_acuerdo'], '2026-10-22')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['lat'])

    def test_undated_definitive_does_not_inherit_initial_date(self):
        row = Adapter.parse_projects(page(section(dated=False)))[0]
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertIsNone(row['fecha_acuerdo'])

    def test_missing_expediente_uses_document_dossier(self):
        row = Adapter.parse_projects(page(section('Aprovació del projecte de reforma')))[0]
        self.assertIsNone(row['expediente'])
        self.assertEqual(row['id'], 'llagostera-proy-docs-123')

    def test_multiple_projects_keep_documents_separate(self):
        second = section('Aprovació del projecte de camí (exp 2026/13)').replace('/123/', '/124/')
        rows = Adapter.parse_projects(page(section() + second))
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['source_dossier_id'] for r in rows], ['123', '124'])

    def test_reject_navigation_forms_and_incomplete_project(self):
        for content in ['<a href="/form">Sol·licitud de llicència</a>', section().replace('Projecte aprovació', 'Edicte aprovació')]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                Adapter.parse_projects(page(content))

    def test_reject_pagination_unassigned_docs_and_duplicates(self):
        for content in [section() + '<a rel="next" href="?page=2">2</a>',
                        doc('Projecte sense títol', 'orphan') + section(), section() + section()]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                Adapter.parse_projects(page(content))

    def test_reject_foreign_or_mixed_document_provenance(self):
        for content in [section().replace('seu-e.cat', 'example.com'),
                        section().replace('/123/final', '/999/final')]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                Adapter.parse_projects(page(content))

    def test_manifest_loader_and_disabled_licences(self):
        manifest = load_manifest('llagostera')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_update_refreshes_snapshot(self):
        adapter = Adapter('llagostera')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 15}) as fetch:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 15})
            fetch.assert_called_once_with(Path('out'))


if __name__ == '__main__':
    unittest.main()
