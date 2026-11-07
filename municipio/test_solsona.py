import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.solsona import SOURCE, SolsonaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


TITLE = 'Projecte de rehabilitació de les pistes esportives'
URL = SOURCE + '/pistes'


def inventory(items, navigation=''):
    return '<div id="content-core">' + ''.join(
        f'<article class="tileItem"><h2 class="tileHeadline"><a href="{url}">{title}</a></h2></article>'
        for title, url in items) + navigation + '</div>'


def detail(title=TITLE, docs=('memoria.pdf', 'planols.pdf')):
    return f'<h1 class="documentFirstHeading">{title}</h1><div id="content-core">' + ''.join(
        f'<a href="{URL}/{doc}">{doc}</a>' for doc in docs) + '</div>'


class SolsonaTests(unittest.TestCase):
    def test_physical_projects_only_and_canonical_deduplication(self):
        entries, pages = Adapter.parse_inventory(inventory([
            (TITLE, URL + '/view'), (TITLE, URL),
            ('Sol·licitud de llicència', SOURCE + '/form'),
            ('Licitació de les obres', SOURCE + '/contract'),
            ('Notícia municipal', SOURCE + '/news')]))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['url'], URL)
        self.assertEqual(pages, [])

    def test_documents_grouped_and_dates_unknown(self):
        row = Adapter.parse_detail(detail(), {'titulo': TITLE, 'url': URL, 'detail_url': URL + '/view'})
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '25207')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['fase'], 'exposición pública')
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail(docs=()), {'titulo': TITLE, 'url': URL})

    def test_pagination_crawled_and_records_deduplicated(self):
        second = SOURCE + '?b_start:int=20'
        other = SOURCE + '/carrer'
        title2 = "Projecte d'urbanització del carrer"
        pages = {
            SOURCE: inventory([(TITLE, URL)], f'<div class="listingBar"><a href="{second}">Següent</a></div>'),
            second: inventory([(TITLE, URL + '/view'), (title2, other)],
                              f'<div class="listingBar"><a href="{SOURCE}">Anterior</a></div>'),
            URL + '/view': detail(),
            other: detail(title2),
        }
        adapter = Adapter('solsona')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            output = Path(directory) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len({row['id'] for row in rows}), 2)

    def test_fail_closed_without_replacing_prior_snapshot(self):
        adapter = Adapter('solsona')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            output.write_text('prior snapshot')
            with patch.object(adapter, '_fetch', return_value='<html>Access denied</html>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'prior snapshot')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory([], '<a rel="next" href="https://example.org">Next</a>'))
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail('Login'), {'titulo': TITLE, 'url': URL})

    def test_manifest_and_licences_disabled(self):
        manifest = load_manifest('solsona')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Solsona', 'Lleida', '25207'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licences.jsonl'
            self.assertEqual(Adapter('solsona').backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
