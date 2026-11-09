import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ferreries import BASE, SOURCE, SECTIONS, FerreriesAyuntamientoAdapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title, body):
    return f'<div class="PLA_ntilla"><h1>{title}</h1><div class="PLA_texte">{body}</div></div>'


def inventory():
    return page('PGOU', ''.join(f'<a href="/Contingut.aspx?IdPub={i}">{title}</a>'
                               for i, title in enumerate(sorted(SECTIONS), 60)))


class FerreriesTests(unittest.TestCase):
    def test_inventory_requires_full_sections_and_rejects_pagination(self):
        self.assertEqual(len(FerreriesAyuntamientoAdapter.parse_inventory(inventory())), 5)
        for html in [page('PGOU', ''), '<h1>PGOU</h1>', inventory() + '<a rel="next" href="?page=2">2</a>']:
            with self.assertRaises(ValueError):
                FerreriesAyuntamientoAdapter.parse_inventory(html)

    def test_document_scope_provenance_and_dedup(self):
        section = {'titulo': 'ISA', 'url': BASE + '/Contingut.aspx?IdPub=60'}
        html = page('PGOU - ISA', '<a href="/plan.pdf">Memòria ambiental</a>'
                    '<a href="/plan.pdf">duplicate</a><a href="/isa.rar"></a>')
        html += '<a href="/budget.pdf">Budget outside content</a>'
        docs = FerreriesAyuntamientoAdapter.parse_documents(html, section)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['url_procedencia'], section['url'])
        self.assertEqual(docs[1]['titulo'], 'isa.rar')
        for body in ['', '<a href="https://example.com/plan.pdf">Plan</a>', '<a href="?page=2">Next page</a>']:
            with self.assertRaises(ValueError):
                FerreriesAyuntamientoAdapter.parse_documents(page('PGOU - ISA', body), section)

    def test_snapshot_one_instrument_no_inferred_dates_or_coordinates(self):
        adapter = FerreriesAyuntamientoAdapter()
        sections = adapter.parse_inventory(inventory())
        pages = {SOURCE: inventory()}
        for section in sections:
            pages[section['url']] = page('PGOU - ' + section['titulo'],
                '<a href="/common.pdf">Publicació 12 maig 2026</a>'
                f'<a href="/unique-{section["titulo"]}.pdf">Cartografia</a>')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(rows[0]['documentos']), 6)
            self.assertEqual(len(rows[0]['documentos'][0]['procedencias']), 5)
            for key in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry', 'fase']:
                self.assertIsNone(rows[0][key])
            original = out.read_text()
            with patch.object(adapter, '_fetch', return_value='<h1>Unavailable</h1>'):
                with self.assertRaises(ValueError): adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('ferreries')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), FerreriesAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
