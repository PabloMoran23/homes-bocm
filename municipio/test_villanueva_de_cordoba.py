import tempfile
import unittest
from pathlib import Path

from municipio.adapters.villanueva_de_cordoba import (
    SOURCE, VillanuevaDeCordobaAyuntamientoAdapter, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest

PGOU = 'Plan General de Ordenación Urbanística de Villanueva de Córdoba'
AVANCE = ('Avance de identificación y delimitación de asentamientos urbanísticos '
          'y ámbitos de hábitat rural diseminado en suelo no urbanizable.')


def inventory(links):
    return '<div class="entry-content"><p>NORMAS URBANÍSTICAS DE VILLANUEVA DE CÓRDOBA</p>' + links + '</div>'


def link(title, url):
    return f'<a href="{url}">{title}</a>'


class InventoryTests(unittest.TestCase):
    def test_plans_group_documents_and_exclude_other_content(self):
        html = inventory(
            link(PGOU, 'http://www.juntadeandalucia.es/boja/plan.pdf')
            + link(PGOU + '.', 'https://www.juntadeandalucia.es/boja/plan.pdf')
            + link(PGOU, 'https://www.juntadeandalucia.es/boja/annex.pdf')
            + link(AVANCE, 'https://bop.dipucordoba.es/avance.pdf')
            + link('Ordenanza de obras menores y licencias', '/ordenanza.pdf')
            + link('Solicitud de licencia de obra', '/solicitud.pdf')
            + link('Inventario Toponímico de asentamientos', '/toponimia/')
            + link('Anuncio de licitación de obras', '/licitacion.pdf'))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['url_documento'], 'https://www.juntadeandalucia.es/boja/plan.pdf')
        self.assertEqual(rows[0]['documentos'][0]['url_inventario'], 'http://www.juntadeandalucia.es/boja/plan.pdf')
        self.assertEqual(rows[0]['url'], SOURCE)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '14069')
            for field in ('fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertIsNone(row[field])
        self.assertEqual(rows[0]['id'], parse_inventory(inventory(link(PGOU, '/new.pdf')))[0]['id'])

    def test_fail_closed(self):
        for html in ('<html>Maintenance</html>', inventory(link('Ordenanza fiscal', '/tax.pdf')),
                     inventory(link(PGOU, 'https://example.org/a.pdf')),
                     inventory(link(PGOU, '/formulario/')),
                     inventory(link(PGOU, '/a.pdf') + '<div class="page-links">2</div>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('villanueva-de-cordoba')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, VillanuevaDeCordobaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
