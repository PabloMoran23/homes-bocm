"""Offline tests use minimal source-shaped HTML; never require local evidence."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.canovelles import CanovellesAyuntamientoAdapter as Adapter


def doc(uid, label):
    return f'<li><a href="/documents/2562153/123/{label}/{uid}">{label}</a></li>'


def page(body):
    return '<div class="journal-content-article"><div><h4>ANY 2025</h4>' + body + '</div></div>'


class CanovellesTests(unittest.TestCase):
    def test_groups_documents_and_does_not_invent_dates(self):
        html = page('<p><strong>Projecte de reforma del pavelló</strong></p><ul>' +
                    doc('notice', "Anunci d'aprovació inicial") +
                    doc('notice2', "Anunci d'aprovació definitiva") +
                    '</ul><p>Documentació tècnica</p><ul>' +
                    doc('technical', 'Projecte') + doc('plans', 'Plànols') + '</ul>')
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertEqual(row['anio_seccion_inventario'], 2025)
        self.assertEqual(row['codigo_ine'], '08041')
        for key in ('fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        changed = html.replace('ANY 2025', 'ANY 2026').replace('reforma del pavelló', 'Reforma del pavelló actualitzada')
        self.assertEqual(row['id'], Adapter.parse_projects(changed)[0]['id'])

    def test_multiple_projects_and_exclusions(self):
        html = page(''.join('<p><strong>' + title + '</strong></p><ul>' + doc(str(i), 'Document tècnic') + '</ul>'
                            for i, title in enumerate([
                                'Projecte de millora del carrer',
                                "Projecte d'activitats del pavelló",
                                "Proposta d'estructura de costos del servei",
                                "Restauració de la façana de l'Església"])))
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertTrue(all(r['fase'] is None for r in rows))

    def test_rejects_navigation_forms_and_notice_without_project_document(self):
        for html in ('<a href="/form">Sol·licitud de llicència</a>',
                     page('<p><strong>Projecte de reforma</strong></p><ul>' + doc('n', 'Anunci') + '</ul>')):
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_fails_on_pagination_unassigned_docs_or_unreviewed_heading(self):
        valid = page('<p><strong>Projecte de reforma</strong></p><ul>' + doc('t', 'Projecte') + '</ul>')
        for html in (valid + '<a rel="next" href="?page=2">2</a>',
                     valid + '<button>Següent</button>',
                     valid + '<script>var options={serverSide:true}</script>',
                     page('<ul>' + doc('t', 'Projecte') + '</ul>'),
                     valid.replace('Projecte de reforma', 'Una notícia')):
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_snapshot_update_and_disabled_licences(self):
        adapter = Adapter('canovelles')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 35}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('x'), Path('state')), {'rows': 35})
            backfill.assert_called_once_with(Path('x'))
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
