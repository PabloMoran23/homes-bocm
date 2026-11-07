import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.benifaio import (
    BenifaioAyuntamientoAdapter, INVENTORY_URL, extract_inventory, parse_directory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def listing(*links):
    return '<h1>Index of /auto/urbanismo/reg-planeamiento/test</h1>' + ''.join(
        f'<a href="{href}">{title}</a>' for href, title in links
    )


class BenifaioTests(unittest.TestCase):
    def test_listing_scope_encoding_and_dedup(self):
        html = listing(('?C=N;O=D', 'Name'), ('../', 'Parent Directory'),
                       ('https://example.org/form.pdf', 'Solicitud'),
                       ('46060-1001%20CAT%c1LOGO/', '46060-1001 CATÁLOGO/'),
                       ('46060-1001%20CAT%c1LOGO/', '46060-1001 CATÁLOGO/'))
        links = parse_directory(html, INVENTORY_URL)
        self.assertEqual(len(links), 1)
        self.assertIn('%C1', links[0]['url'])
        self.assertIn('CATÁLOGO', links[0]['titulo'])

    def test_recursive_grouping_and_provenance(self):
        root = INVENTORY_URL
        pages = {
            root: listing(('general/', '1 P. GENERAL/')),
            root+'general/': listing(('pg/', '46060-1000 PG BENIFAIÓ 2020-0365/'),
                                     ('annotation/', '46060-1000B Anot.1_PGE ejecuc sentencia/'),
                                     ('catalogue/', '46060-1001 2021-0241 CATÁLOGO DEL PG/')),
            root+'general/pg/': listing(('memoria.pdf', 'Memoria'), ('planos/', '4 PLANOS/')),
            root+'general/pg/planos/': listing(('plano.pdf', 'Plano')),
            root+'general/annotation/': listing(('sentencia.pdf', 'Sentencia 13-07-2023')),
            root+'general/catalogue/': listing(('catalogo.pdf', 'Catálogo')),
        }
        rows, visited = extract_inventory(pages.__getitem__)
        self.assertEqual(len(visited), len(pages))
        self.assertEqual(len(rows), 2)
        pg, catalogue = rows
        self.assertEqual(len(pg['documentos']), 3)
        self.assertEqual(len(pg['entradas_registro']), 2)
        self.assertEqual(len(catalogue['documentos']), 1)
        self.assertEqual(pg['documentos'][1]['inventory_url'], root+'general/annotation/')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '46060')
            for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, row)

    def test_reject_changed_empty_paginated_or_orphan_source(self):
        for html in ('<h1>Login</h1>', listing(),
                     listing(('a.pdf', 'Documento'))+'<a rel="next" href="?page=2">Next</a>',
                     listing(('unexpected.html', 'Unexpected'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_directory(html, INVENTORY_URL)
        with self.assertRaises(ValueError):
            extract_inventory(lambda u: listing(('documento.pdf', 'Documento')))
        pages = {INVENTORY_URL: listing(('annotation/', '46060-1000B Anot.1/')),
                 INVENTORY_URL+'annotation/': listing(('doc.pdf', 'Acuerdo'))}
        with self.assertRaises(ValueError):
            extract_inventory(pages.__getitem__)

    def test_manifest_and_disabled_licences(self):
        raw = load_yaml(Path('data/municipios/benifaio/manifest.yaml'))
        self.assertEqual(raw['codigo_ine'], '46060')
        self.assertEqual(raw['provincia'], 'Valencia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        manifest = load_manifest('benifaio')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, BenifaioAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get') as get:
            out = Path(tmp) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')
            get.assert_not_called()

    def test_network_failure_does_not_replace_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous output')
            adapter = BenifaioAyuntamientoAdapter('benifaio')
            with patch('requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous output')


if __name__ == '__main__':
    unittest.main()
