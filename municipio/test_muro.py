"""Offline parser and crawl-contract tests; no network or evidence files required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.muro import (
    BASE, INVENTORIES, MuroAyuntamientoAdapter, make_record,
    parse_documents, parse_listing,
)
from municipio.manifest import load_manifest


def listing(items, pager=''):
    cards = ''.join(f'<a href="{url}"><h3>{title}</h3><p>{count} documents</p></a>'
                    for url, title, count in items)
    return f'<main><div class="taxonomy-term-files">{cards}</div>{pager}</main>'


def document(title='Memòria', filename='one.pdf', date='01/10/2018'):
    return (f'<main><section class="multimedia--documents"><div><h3>{title}</h3>'
            f'<span>PDF · {date}</span><a href="/sites/cilma_muro/files/{filename}">'
            'Descarregar</a></div></section></main>')


class MuroTests(unittest.TestCase):
    def test_manifest(self):
        m = load_manifest('muro')
        self.assertEqual((m.nombre, m.provincia), ('Muro', 'Illes Balears'))
        self.assertFalse(m.licencias.enabled)
        self.assertEqual(m.portal.adapter, 'municipio.adapters.muro:MuroAyuntamientoAdapter')

    def test_inventory_scoped_and_pagination(self):
        html = '<a href="/wrong"><h3>Estudi de Detall fake menu</h3></a>' + listing(
            [('/plan', 'Estudi de Detall carrer', 3)], '<a href="?page=1">Següent</a>')
        cards, pages = parse_listing(html, INVENTORIES[0])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['count'], 3)
        self.assertEqual(pages, [INVENTORIES[0] + '?page=1'])

    def test_document_date_is_not_approval_or_publication(self):
        docs = parse_documents(document(), BASE + '/plan')
        self.assertEqual(docs[0]['fecha_documento_portal'], '2018-10-01')
        row = make_record({'titulo': 'Estudi de Detall carrer', 'url': BASE + '/plan', 'count': 1}, INVENTORIES[0], docs)
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])
        self.assertIsNone(row['fase'])
        self.assertFalse(row['publication_ready'])

    def test_reject_missing_inventory_unsafe_urls_and_forms(self):
        with self.assertRaises(ValueError):
            parse_listing('<html>Maintenance</html>', INVENTORIES[0])
        with self.assertRaises(ValueError):
            parse_listing(listing([('https://example.org/plan', 'Estudi de Detall', 1)]), INVENTORIES[0])
        with self.assertRaises(ValueError):
            make_record({'titulo': 'Model instància llicència urbanística'}, INVENTORIES[0], [])
        with self.assertRaises(ValueError):
            parse_documents(document(date='31/02/2018'), BASE + '/plan')

    def test_crawl_all_pages_group_docs_update_and_no_partial_write(self):
        plan, child, exposure = BASE + '/plan', BASE + '/child', BASE + '/exposure'
        sources = {
            INVENTORIES[0]: listing([(plan, 'Estudi de Detall carrer', 1),
                                    ('/viewer', 'Sistema Informació', 0)]),
            plan: listing([(child, 'Memòria', 1)]), child: document(),
            INVENTORIES[1]: listing([('/form', 'Model instància', 1)], '<a href="?page=1">2</a>'),
            INVENTORIES[1] + '?page=1': listing([(exposure, 'EXPOSICIÓ PÚBLICA EXP. 2/2018. ESTUDI DE DETALL PARCEL·LA 443', 2)],
                                               '<a href="?page=0">Anterior</a>'),
            INVENTORIES[1] + '?page=0': listing([], '<a href="?page=1">2</a>'),
            exposure: document().replace('</main>', '') + document('Plànol', 'two.pdf').replace('<main>', ''),
        }
        seen = []
        def fetch(url):
            seen.append(url)
            return sources[url]
        adapter = MuroAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=fetch):
            output = Path(directory) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertIn(INVENTORIES[1] + '?page=1', seen)
            self.assertEqual(len(rows[1]['documentos']), 2)
            self.assertEqual(rows[1]['expediente'], '2/2018')
            self.assertEqual(rows[1]['fase'], 'exposición pública')
            self.assertEqual(rows[0]['documentos'][0]['pagina_fuente'], child)
            original = output.read_text()
            adapter.update_proyectos(output, Path(directory) / 'unused-state')
            self.assertEqual(output.read_text(), original)
            sources[exposure] = document()  # Claimed second attachment disappeared.
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)


if __name__ == '__main__':
    unittest.main()
