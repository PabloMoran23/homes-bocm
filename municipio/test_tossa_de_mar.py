"""Offline semantic and failure tests; fixtures reproduce the observed table."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tossa_de_mar import SOURCE, TossaDeMarAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def link(title, number=1, href=None):
    target = href or f'https://tossademar.eadministracio.cat/preview-document/00000000-0000-0000-0000-{number:012d}'
    return f'<tr><td><a class="gIconLink" href="{target}">{title}</a></td></tr>'


def page(links, extra=''):
    return ('<div id="content"><span>2.1. PROJECTES EN TRAMITACIÓ</span>'
            '<table class="TransparencyListPanel"><tbody>' + links + '</tbody></table>' + extra + '</div>')


class TossaTests(unittest.TestCase):
    def test_real_project_and_unknown_semantics(self):
        rows = parse_inventory(page(link('PROJECTE-MUSEU_Proj_Executiu')))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '17202')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['documentos'][0]['titulo'], 'PROJECTE-MUSEU_Proj_Executiu')

    def test_group_phases_retain_links_and_stable_identity(self):
        first = link('PROJECTE RECUPERACIÓ CAMI RONDA PORTO PI - Fase 1', 1)
        second = link('PROJECTE RECUPERACIÓ CAMI RONDA PORTO PI - Fase 2', 2)
        rows = parse_inventory(page(first + second + first))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['id'], parse_inventory(page(second + first))[0]['id'])
        self.assertEqual(rows[0]['id'], parse_inventory(page(second))[0]['id'])

    def test_group_document_variants(self):
        rows = parse_inventory(page(link('PROJECTE-MUSEU_Proj_Basic', 1) + link('PROJECTE-MUSEU_Proj_Executiu', 2)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_exclude_ordinance_forms_tenders_and_navigation(self):
        html = page(link('Ordenança fiscal', 1) + link('Sol·licitud de llicència', 2)
                    + link('PROJECTE anunci de licitació', 3) + link('Projectes en tràmit', 4)
                    + link('PROJECTE-BIBLIOTECA_Proj_Bàsic', 5))
        self.assertEqual(len(parse_inventory(html)), 1)

    def test_empty_or_login_rejected(self):
        for html in ('<h1>Identifica’t</h1>', page(link('Ordenança fiscal'))):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected(self):
        for control in ('<a rel="next" href="?page=2">2</a>', '<div class="pagination">1 2</div>', '<button>Següent</button>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(page(link('PROJECTE-MUSEU_Proj_Executiu'), control))

    def test_unresolved_project_folder_or_foreign_document_rejected(self):
        for target in ('#', 'https://example.org/preview-document/00000000-0000-0000-0000-000000000001'):
            with self.assertRaises(ValueError):
                parse_inventory(page(link('PROJECTE-MUSEU', href=target)))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tossa-de-mar')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = TossaDeMarAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(output.read_text(), '')

    def test_update_refreshes_snapshot(self):
        adapter = TossaDeMarAyuntamientoAdapter()
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 6}) as fetch:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 6})
            fetch.assert_called_once_with(Path('out'))


if __name__ == '__main__':
    unittest.main()
