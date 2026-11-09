"""Offline parser and complete-traversal tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alcala_del_valle import (
    AlcalaDelValleAyuntamientoAdapter, BASE, INVENTORY,
    official_url, parse_instrument, parse_inventory, supported_title,
)
from municipio.manifest import load_manifest, load_yaml

TITLE = 'Innovación por modificación puntual del suelo no urbanizable del PGOU de Alcalá del Valle'
OTHER = 'Apertura de Consulta Pública Previa para la Modificación puntual en suelo rústico del planeamiento urbanístico de Alcalá del Valle'


def listing(page=1, total=1, next_href=None, title=TITLE, identity='199'):
    next_link = f'<a class="next" href="{next_href}">Siguiente</a>' if next_href else ''
    return f'''<main><div class="com-content-category"><table><tr>
    <th class="list-title"><a href="/noiticias/{identity}-instrumento">{title}</a></th>
    <th class="list-title"><a href="/noiticias/1-formulario">Modelo de solicitud de licencia de obras</a></th>
    </tr></table><p class="counter">Página {page} de {total}</p>{next_link}</div></main>'''


def detail(title=TITLE, docs=('borrador.pdf', 'ambiental.pdf')):
    links = ''.join(f'<a href="/images/Documentacion/{name}">{name}</a>' for name in docs)
    return f'<main><h1>{title}</h1>{links}</main><footer><a href="/otra.pdf">No incluir</a></footer>'


class AlcalaDelValleTests(unittest.TestCase):
    def test_encoded_official_urls(self):
        url = BASE + '/noiticias/199-innovaci%C3%B3n'
        self.assertEqual(official_url(url, '/noiticias/199-innovación'), url)

    def test_document_grouping_and_provenance(self):
        row = parse_instrument(detail(docs=('borrador.pdf', 'ambiental.pdf', 'borrador.pdf')), BASE + '/noiticias/199-instrumento', '199')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '11002')
        self.assertEqual(row['documentos'][0]['source_url'], row['url'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['geometry_status'], 'unavailable')
        for field in ['fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, row)

    def test_exclusions(self):
        for title in ['Modelo de solicitud de licencia', 'Licitación modificación puntual PGOU',
                      'El Ayuntamiento habilita el portal web sobre el Planeamiento Urbanístico Municipal',
                      'Oferta de empleo público', 'Aprobación de pliegos de obras']:
            self.assertFalse(supported_title(title))
        rows, next_url, _, _ = parse_inventory(listing(), INVENTORY)
        self.assertEqual(list(rows), ['199'])
        self.assertIsNone(next_url)

    def test_fail_closed_on_layout_or_missing_documents(self):
        for html in ['', '<main>captcha</main>', listing().replace('Página 1 de 1', '')]:
            with self.assertRaises(ValueError):
                parse_inventory(html, INVENTORY)
        for html in [detail(docs=()), '<main><h1>Noticia sin relación</h1></main>']:
            with self.assertRaises(ValueError):
                parse_instrument(html, BASE + '/noiticias/199-instrumento', '199')

    def test_incomplete_pagination_and_external_links_fail(self):
        for html in [listing(1, 2), listing(next_href='/noticias?start=10'),
                     listing(1, 2, 'https://example.org/noticias?start=10')]:
            with self.assertRaises(ValueError):
                parse_inventory(html, INVENTORY)

    def test_full_snapshot_follows_pages_and_keeps_instruments_separate(self):
        adapter = AlcalaDelValleAyuntamientoAdapter('alcala-del-valle')
        pages = {
            INVENTORY: listing(1, 2, '/noticias?start=10'),
            INVENTORY + '?start=10': listing(2, 2, title=OTHER, identity='218'),
            BASE + '/noiticias/199-instrumento': detail(),
            BASE + '/noiticias/218-instrumento': detail(OTHER, ('consulta.pdf',)),
        }
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(result['count'], 2)
            self.assertEqual([len(row['documentos']) for row in rows], [2, 1])
            self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_cycles_or_skipped_pages_do_not_replace_output(self):
        adapter = AlcalaDelValleAyuntamientoAdapter('alcala-del-valle')
        for html in [listing(1, 2, '/noticias'), listing(2, 2)]:
            with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', return_value=html):
                path = Path(directory) / 'proyectos.jsonl'
                path.write_text('previous snapshot')
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('alcala-del-valle')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '11002')
        self.assertEqual(manifest.provincia, 'Cádiz')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = AlcalaDelValleAyuntamientoAdapter(manifest.slug).backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
