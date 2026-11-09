import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.agramunt import (
    AgramuntAyuntamientoAdapter, SOURCE, parse_documents, parse_inventory, semantics,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(body, heading='Informació Urbanística'):
    return f'<article id="content"><h1>{heading}</h1><div id="content-core">{body}</div></article>'


def tile(path='poum', title='POUM - Pla', description='Instrument urbanístic municipal'):
    return f'<article class="tileItem"><h2 class="tileHeadline"><a href="{SOURCE}/{path}">{title}</a></h2><span class="description">{description}</span></article>'


def document(name='Memòria', path='memoria.pdf/view'):
    return f'<a href="{SOURCE}/poum/{path}">{name}</a>'


class AgramuntTests(unittest.TestCase):
    def test_dates_are_distinct_and_laws_excluded(self):
        result = semantics("Aprovació definitiva del Text refós, en data 20 de setembre de 2023 i acordada la seva publicació a efectes d’executivitat, en sessió de data 31 de gener de 2024. Publicat al DOGC número 9119, de data 11 de març de 2024.")
        self.assertEqual(result['fecha_aprob'], '2023-09-20')
        self.assertEqual(result['fecha_publicacion'], '2024-03-11')
        self.assertEqual(result['acuerdos'][-1]['fecha_acuerdo'], '2024-01-31')
        result = semantics("Decret llei 1/2009, de data 22 de desembre de 2009. Aprovada definitivament per la Comissió Territorial en sessió de data 23 de juliol de 2025.")
        self.assertEqual(len(result['acuerdos']), 1)
        self.assertEqual(result['fecha_aprob'], '2025-07-23')
        self.assertEqual(semantics('Document redactat el 16 de desembre de 2024')['fecha_aprob'], None)

    def test_initial_and_provisional(self):
        result = semantics("Acord de l’Ajuntament Ple, de data 30 de gener de 2025, de l’aprovació inicial de la Modificació puntual.")
        self.assertEqual(result['fase'], 'aprobación inicial')
        self.assertEqual(result['fecha_aprob'], '2025-01-30')
        result = semantics("Aprovat provisionalment per l'Ajuntament-Ple en data 30 d'octubre de 2025.")
        self.assertEqual(result['fecha_aprob'], '2025-10-30')

    def test_fail_closed_and_no_forms(self):
        for html in ['<h1>Login</h1>', page(''), page(tile(title='Sol·licitud de llicència'))]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_inventory(page(tile().replace(SOURCE + '/poum', 'https://example.org/plan')))
        with self.assertRaises(ValueError):
            parse_documents(page('<a class="contenttype-folder" href="subfolder">Nested</a>'), SOURCE + '/poum')

    def test_documents_group_and_deduplicate(self):
        docs, following = parse_documents(page(document() + document() + document('Plànol', 'mapa.pdf') + '<a href="#collapse">panel</a>'), SOURCE + '/poum')
        self.assertEqual(len(docs), 2)
        self.assertIsNone(following)
        self.assertEqual(docs[0]['source_url'], SOURCE + '/poum')

    def test_full_paginated_snapshot_and_stable_ids(self):
        pages = {
            SOURCE: page(tile() + '<a rel="next" href="?b_start:int=1">Next</a>'),
            SOURCE + '?b_start:int=1': page(tile('modificacio', 'Modificació del POUM') + '<div class="listingBar"><a href="?b_start:int=0">1</a></div>'),
            SOURCE + '/poum': page(document() + '<a rel="next" href="?b_start:int=1">Next</a>'),
            SOURCE + '/poum?b_start:int=1': page(document('Plànol', 'mapa.pdf')),
            SOURCE + '/modificacio': page(document('Aprovació inicial Ajuntament Ple 27.11.2025')),
        }
        adapter = AgramuntAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(directory) / 'out.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 2)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[1]['fecha_aprob'], '2025-11-27')
            self.assertIsNone(rows[0]['geometry'])
            self.assertIsNone(rows[0]['fecha_publicacion'])
            adapter.update_proyectos(out, Path(directory) / 'state')
            self.assertEqual(rows, [json.loads(line) for line in out.read_text().splitlines()])
            pages[SOURCE] = page(tile() + '<a rel="next" href="' + SOURCE + '">Next</a>')
            before = out.read_bytes()
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(before, out.read_bytes())

    def test_unknown_pagination_and_missing_documents(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(tile() + '<div class="pagination"><a href="?page=2">2</a></div>'))
        adapter = AgramuntAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=[page(tile()), page('No documents', 'POUM')]):
            out = Path(directory) / 'out.jsonl'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('agramunt')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, AgramuntAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '25003')
        self.assertEqual(raw['provincia'], 'Lleida')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
