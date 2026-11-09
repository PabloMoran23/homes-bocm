"""Offline semantic and completeness checks; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_coloma_de_cervello import (
    BASE, INVENTORIES, SantaColomaDeCervelloAyuntamientoAdapter as Adapter, dates,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(body, extra=''):
    return '<div class="journal-content-article"><div>' + body + '</div></div>' + extra


def doc(folder='123', label='Memòria', suffix='a'):
    return f'<a href="/documents/28421/{folder}/projecte.pdf/{suffix}">{label}</a>'


class ParserTests(unittest.TestCase):
    def test_groups_all_parts_and_mixed_case_heading(self):
        html = inventory('<p><strong>PLA PARCIAL DE TORRE SALBANA</strong>' + doc() + '</p>'
                         '<p>' + doc(label='Plànols', suffix='b') + '</p>'
                         '<p><strong>MODIFICACIÓ PUNTUAL DEL PLA GENERAL METROPOLITÀ (aprovació provisional)</strong></p>'
                         '<p>' + doc('456') + '</p>')
        rows = Adapter.parse_inventory(html, BASE + INVENTORIES[0])
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertTrue(rows[0]['documentos'][0]['url'].startswith('https://seu-e.cat/documents/'))

    def test_dates_retain_context_and_do_not_use_footer_or_filenames(self):
        html = inventory('<p><u>MILLORA DEL SOBREXEIDOR DE LA RIERA DE CAN LLUCH</u></p>'
                         '<p>' + doc(label='Anunci (BOPB 07/08/2026)') + '</p>'
                         '<p>Certificat d’acord (8 de maig 2026)</p>'
                         '<p>Acord de Ple (abril 2024)</p>')
        html += '<div class="datatable_info_footer">Actualització: 22/10/2026</div>'
        row = Adapter.consolidate(Adapter.parse_inventory(html, BASE + INVENTORIES[2]))[0]
        self.assertEqual([(e['tipo'], e['fecha']) for e in row['eventos']],
                         [('publicacion', '2026-08-07'), ('acuerdo', '2026-05-08')])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['lat'])
        self.assertEqual(dates('31/02/2026; abril 2024; 19 de juny de 2025'), ['2025-06-19'])

    def test_same_instrument_across_inventories(self):
        rows = []
        for title, source, part in [
            ('APROVACIÓ INICIAL DEL PROJECTE DE REPARCEL·LACIÓ FONT VELLA PAU-1', INVENTORIES[0], 'initial'),
            ('TEXT REFÓS DEL PROJECTE DE REPARCEL·LACIÓ FONT VELLA PAU 1', INVENTORIES[1], 'final'),
        ]:
            rows.extend(Adapter.parse_inventory(inventory('<p><u>' + title + '</u></p><p>' + doc('18483973', suffix=part) + '</p>'), BASE + source))
        result = Adapter.consolidate(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['documentos']), 2)
        self.assertEqual(len(result[0]['source_urls']), 2)
        self.assertEqual(len(result[0]['titulos_fuente']), 2)
        self.assertEqual(result[0]['id'], Adapter.consolidate(rows[::-1])[0]['id'])

    def test_rejects_empty_forms_pagination_and_orphan_links(self):
        valid = '<p><u>PROJECTE EXECUTIU DE MILLORA DEL CARRER</u></p><p>' + doc() + '</p>'
        for html in [
            '<html>Login</html>',
            inventory('<p>Sol·licitud de llicència</p>' + doc()),
            inventory(valid, '<a rel="next" href="?page=2">2</a>'),
            inventory(valid, '<div class="pagination"><a href="?page=2">2</a></div>'),
            inventory(valid + '<div>' + doc('789') + '</div>'),
            inventory('<p><u>PROJECTE SENSE DOCUMENTACIÓ PUBLICADA</u></p>' + valid),
        ]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html, BASE + INVENTORIES[0])

    def test_update_refresh_and_failure_preserves_output(self):
        adapter = Adapter('santa-coloma-de-cervello')
        with patch.object(adapter, 'backfill_proyectos', return_value={'status': 'ok'}) as call:
            adapter.update_proyectos(Path('out'), Path('state'))
            call.assert_called_once_with(Path('out'))
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'out.jsonl'
            out.write_text('previous\n')
            with patch('municipio.adapters.santa_coloma_de_cervello.requests.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('santa-coloma-de-cervello')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Barcelona')


if __name__ == '__main__':
    unittest.main()
