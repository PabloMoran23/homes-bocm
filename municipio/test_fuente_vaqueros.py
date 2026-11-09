"""Offline parser tests; live evidence is generated separately."""
import unittest

from municipio.adapters.fuente_vaqueros import (
    SOURCE, SECTIONS, parse_inventory, parse_documents, parse_projects,
)


def fixtures():
    inventory = '<h2>Documentación urbanística de Fuente Vaqueros</h2>'
    pages = {}
    for key, (label, _) in SECTIONS.items():
        inventory += f'<h4 class="elementor-icon-box-title"><a href="{key}/">{label}</a></h4>'
        pdf = f'/wp-content/uploads/{key}.pdf'
        heading = 'Planos adaptación' if key == 'planos-adaptacion' else label
        pages[key] = f'<h1>{heading}</h1><a href="{pdf}">Descargar</a><a href="{pdf}">Visor</a>'
    return inventory, pages


class FuenteVaquerosParserTests(unittest.TestCase):
    def test_grouping_provenance_and_no_inferred_dates(self):
        inventory, pages = fixtures()
        rows = parse_projects(inventory, pages)
        self.assertEqual(len(rows), 2)
        adaptation, revision = rows
        self.assertEqual(len(adaptation['documentos']), 4)
        self.assertEqual(len(revision['documentos']), 2)
        self.assertEqual({d['titulo'] for d in revision['documentos']},
                         {'Anexo memoria', 'Planos NNSS'})
        for row in rows:
            self.assertEqual(row['codigo_ine'], '18079')
            self.assertFalse(row['publication_ready'])
            self.assertNotIn('lat', row)
            self.assertNotIn('fase', row)
            for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob'):
                self.assertIsNone(row[field])
            for doc in row['documentos']:
                self.assertTrue(doc['source_page'].startswith(SOURCE))

    def test_reject_navigation_only_missing_or_new_sections(self):
        inventory, _ = fixtures()
        for html in ('<a href="planos-nnss/">NNSS</a>',
                     inventory.replace('h4 class="elementor-icon-box-title"', 'h4', 1),
                     inventory + '<h4 class="elementor-icon-box-title"><a href="nuevo/">Nuevo</a></h4>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_fail_on_pagination_in_inventory_or_section(self):
        inventory, pages = fixtures()
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_inventory(inventory + '<a rel="next" href="page/2/">Siguiente</a>')
        pages['anexo-memoria'] += '<div class="pagination">2</div>'
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_projects(inventory, pages)

    def test_reject_forms_external_documents_and_wrong_page(self):
        section = {'titulo': 'Anexo memoria', 'url': SOURCE + 'anexo-memoria/'}
        for html in ('<h1>Anexo memoria</h1><a href="/licencia.doc">Solicitud</a>',
                     '<h1>Anexo memoria</h1><a href="https://example.org/x.pdf">PDF</a>',
                     '<h1>Inicio</h1><a href="/wp-content/uploads/x.pdf">PDF</a>'):
            with self.assertRaises(ValueError):
                parse_documents(html, section)

    def test_stable_ids_on_reordered_inventory(self):
        inventory, pages = fixtures()
        rows = parse_projects(inventory, pages)
        heading, *cards = inventory.split('<h4')
        reordered = heading + ''.join('<h4' + card for card in reversed(cards))
        revised = parse_projects(reordered, pages)
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in revised])


if __name__ == '__main__':
    unittest.main()
