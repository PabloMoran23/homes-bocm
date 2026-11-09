"""Offline parser and adapter contract tests (no network)."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.mercadal_es import (
    MercadalEsAyuntamientoAdapter, SOURCES, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def page(title, links, extra=''):
    return ('<div class="PLA_titol">' + title + '</div><div class="PLA_texte">' +
            ''.join(f'<a href="{href}">{label}</a>' for label, href in links) + extra + '</div>')


NS = page('NORMES SUBSIDIÀRIES VIGENTS', [
    ('Quadre resum NS Planejament urbanístic', '/summary.pdf'),
    ('Revisió NS 1994', '/revision.pdf'),
    ('Mod. Punt 9 Aprov. definitiva', '/mod9-approval.pdf'),
    ('Mod. Punt 9 Memòria', '/mod9-memory.pdf'),
    ('Estudi detall carrer Rosari Fornells', '/rosari.pdf'),
    ('Sèrie A - estructura', '/Contingut.aspx?IdPub=20375'),
    ('Memòria i normativa', '/Patrimoni/memoria.pdf'),
])
PGOU = page('AVANÇ PLA PGOU MERCADAL', [
    ('RESUM (Març 2012)', '/PGOU/resum març.pdf'),
    ('VOLUM I', '/PGOU/vol1.pdf'),
    ('VOLUM II', '/PGOU/vol2.pdf'),
])


class MercadalTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(NS, SOURCES[0])
        self.assertEqual(len(rows), 3)
        mod = next(r for r in rows if r['id'].endswith('ns-mod-9'))
        self.assertEqual(len(mod['documentos']), 2)
        self.assertTrue(all(d['source_url'] == SOURCES[0] for d in mod['documentos']))
        base = rows[0]
        self.assertEqual(len(base['documentos']), 4)
        self.assertTrue(base['url_documento'].endswith('/revision.pdf'))

    def test_pgou_one_instrument_not_six_projects(self):
        rows = parse_inventory(PGOU, SOURCES[1])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertIn('%20', rows[0]['url_documento'])
        self.assertIn('%C3%A7', rows[0]['url_documento'])
        self.assertEqual(rows[0]['tipo'], 'avance de PGOU')

    def test_no_invented_dates_geometry_or_phase(self):
        for row in parse_inventory(NS, SOURCES[0]) + parse_inventory(PGOU, SOURCES[1]):
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '07037')

    def test_fail_closed(self):
        for html in ('<html>Solicitud de licencia</html>',
                     page('NORMES SUBSIDIÀRIES VIGENTS', []),
                     page('NORMES SUBSIDIÀRIES VIGENTS', [('Anuncio licitación', '/bid.pdf')]),
                     NS.replace('/revision.pdf', 'https://other.example/revision.pdf'),
                     NS.replace('</div>', '<a rel="next" href="?page=2">Next</a></div>')):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES[0])

    def test_stable_ids_and_dedup(self):
        first = parse_inventory(NS, SOURCES[0])
        self.assertEqual(first, parse_inventory(NS, SOURCES[0]))
        repeated = NS[:-6] + '<a href="/mod9-memory.pdf">Mod. Punt 9 Memòria</a></div>'
        self.assertEqual(first, parse_inventory(repeated, SOURCES[0]))

    def test_snapshot_update_and_disabled_licences(self):
        class Response:
            def __init__(self, url, html):
                self.url, self.text, self.content = url, html, html.encode()
            def raise_for_status(self):
                pass
        with TemporaryDirectory() as temp:
            out = Path(temp) / 'projects.jsonl'
            adapter = MercadalEsAyuntamientoAdapter()
            with patch('municipio.adapters.mercadal_es.requests.get', side_effect=[Response(SOURCES[0], NS), Response(SOURCES[1], PGOU)]):
                result = adapter.update_proyectos(out, Path(temp) / 'state.json')
            self.assertEqual(result['rows'], 4)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 4)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('mercadal-es')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07037')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
