import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.blanca import (
    BlancaAyuntamientoAdapter, SOURCE, folder_url, parse_folder,
)
from municipio.manifest import load_manifest, load_yaml


def page(folders=(), docs=()):
    text = 'formTransparencia 7.1. PLANEAMIENTO URBANÍSTICO\n'
    for identifier, title, count in folders:
        fragment = (f"<a onClick='pulsaEpigrafe({identifier})'><div title='{title}'>"
                    f"<span class='badge'>{count}</span></div></a>")
        text += 'html_epigrafes += ' + json.dumps(fragment) + ';\n'
    for identifier, title in docs:
        fragment = f"<tr><td><a onClick='verDoc({identifier})'>{title}</a></td></tr>"
        text += 'jQuery("#tablaDocumentosEnlaces > tbody").append(' + json.dumps(fragment) + ');\n'
    # The live UI closes its section even when the folder is empty.
    text += 'html_epigrafes += "</section>";\n'
    return text


class BlancaTests(unittest.TestCase):
    def test_parser_preserves_document_identity_and_titles(self):
        folders, docs = parse_folder(page([(495, 'Planeamiento General', 2)],
                                         [(88705, 'Planeamiento General')]))
        self.assertEqual(folders[0]['count'], 2)
        self.assertEqual(docs[0]['titulo'], 'Planeamiento General')
        self.assertIn('idDoc=88705', docs[0]['url'])
        self.assertIn('entidad=30011', docs[0]['url'])

    def test_grouping_and_no_inferred_dates_or_coordinates(self):
        pages = {
            SOURCE: page([(495, 'Planeamiento General', 2),
                          (1165, 'PLAN PARCIAL SAN ROQUE II.1', 1),
                          (518, 'SECTOR UBRS-2 - PLAN PARCIAL RUNES', 0)],
                         [(88705, 'Planeamiento General')]),
            folder_url(495): page(docs=[(88707, 'Aprobacion Definitiva PGMO en BORM'),
                                       (88709, 'NORMAS PGMO BLANCA 2011')]),
            folder_url(1165): page(docs=[(368452, 'CERTIFICADO APROBACIÓN DEFINITIVA')]),
            folder_url(518): page(),
        }
        adapter = BlancaAyuntamientoAdapter('blanca')
        with tempfile.TemporaryDirectory() as directory, patch.object(
                adapter, '_fetch', side_effect=lambda session, url: pages[url]):
            path = Path(directory) / 'projects.jsonl'
            report = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(report['rows'], 2)
        self.assertEqual(len(report['source_urls']), 4)
        self.assertEqual(len(report['empty_folders']), 1)
        self.assertEqual([len(row['documentos']) for row in rows], [2, 1])
        self.assertEqual(rows[1]['documentos'][0]['id_documento'], '368452')
        self.assertEqual(rows[0]['id'], 'blanca-plan-495')
        for row in rows:
            for key in ('lat', 'lon', 'geometry', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion'):
                self.assertIsNone(row[key])
            self.assertNotIn('fase', row)

    def test_count_mismatch_does_not_replace_snapshot(self):
        adapter = BlancaAyuntamientoAdapter('blanca')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[
                    page([(495, 'Planeamiento General', 2)]),
                    page(docs=[(88707, 'MEMORIA')])]):
                with self.assertRaisesRegex(ValueError, 'count mismatch'):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_rejects_challenge_navigation_and_pagination(self):
        for html in ('<title>Radware Captcha Page</title>', '<a>Plan General</a>',
                     page() + '<a rel="next" href="?pagina=2">2</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_folder(html)

    def test_nested_folders_fail_explicitly(self):
        adapter = BlancaAyuntamientoAdapter('blanca')
        with tempfile.TemporaryDirectory() as directory, patch.object(
                adapter, '_fetch', side_effect=[
                    page([(495, 'Planeamiento General', 1)]),
                    page([(900, 'Modificaciones', 2)])]):
            with self.assertRaisesRegex(ValueError, 'nested'):
                adapter.backfill_proyectos(Path(directory) / 'out.jsonl')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('blanca')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('30011', 'Blanca', 'Murcia'))
        for section, key in [('schedule', 'enabled'), ('geocode', 'jitter_missing'),
                             ('licencias', 'enabled')]:
            self.assertIs(raw[section][key], False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = BlancaAyuntamientoAdapter('blanca').backfill_licencias(path)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
