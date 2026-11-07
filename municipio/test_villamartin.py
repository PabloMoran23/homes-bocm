"""Offline regression tests for planning identity, grouping and Wicket append pages."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villamartin import (
    SOURCE, HOST, VillamartinAyuntamientoAdapter, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def doc(number, title='Plano de ordenación'):
    return f'<a class="gIconLink" href="https://{HOST}/preview-document/00000000-0000-0000-0000-{number:012d}">{title}</a>'


def folder(title, count):
    return f'''<a class="gIconLink exp" href="#" onclick="wicketAjaxGet('?x=folder',null)">{title}<span class="linkExtraInfo"> ( {count} )</span></a>'''


def page(body, more=False):
    control = '''<div class="more_results"><button onclick="wicketAjaxGet('?x=more',null)">Mostrar más</button></div>''' if more else ''
    return '<table class="TransparencyListPanel">' + body + '</table>' + control


def ajax(body):
    return '<?xml version="1.0"?><ajax-response><component id="row"><![CDATA[' + body + ']]></component><component id="more"><![CDATA[<div class="more_results"></div>]]></component></ajax-response>'


class VillamartinTests(unittest.TestCase):
    def adapter(self):
        return VillamartinAyuntamientoAdapter('villamartin')

    def test_manifest_identity_and_disabled_automation(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/villamartin/manifest.yaml'
        raw = load_yaml(path)
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('11041', 'Villamartín', 'Cádiz'))
        for section, flag in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[section][flag], False)
        self.assertEqual(load_manifest(path).portal.adapter, 'municipio.adapters.villamartin:VillamartinAyuntamientoAdapter')

    def test_folder_count_and_title(self):
        entries, more = parse_page(page(folder('PLAN GENERAL', 63)), SOURCE)
        self.assertEqual(entries[0]['title'], 'PLAN GENERAL')
        self.assertEqual(entries[0]['count'], 63)
        self.assertIsNone(more)

    def test_ajax_preserves_distinct_documents_with_same_title(self):
        entries, more = parse_page(ajax(doc(1) + doc(2)), SOURCE)
        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0]['url'], entries[1]['url'])
        self.assertIsNone(more)

    def test_grouping_pagination_and_no_inferred_dates(self):
        adapter = self.adapter()
        responses = [(page(folder('PLAN GENERAL DE ORDENACION URBANISTICA DE VILLAMARTIN', 2)), SOURCE),
                     (page(doc(1, 'Memoria mayo2018'), more=True), SOURCE + 'plan/'),
                     (ajax(doc(2, 'Anuncio aprobación provisional II')), f'https://{HOST}/?x=more')]
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=responses):
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual((result['count'], result['documents']), (1, 2))
            self.assertEqual(len(rows[0]['documentos'][0]['carpetas']), 1)
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon'):
                self.assertNotIn(field, rows[0])
            self.assertFalse(rows[0]['publication_ready'])

    def test_incomplete_folder_preserves_prior_output(self):
        adapter = self.adapter()
        responses = [(page(folder('PLAN GENERAL', 2)), SOURCE), (page(doc(1)), SOURCE + 'plan/')]
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=responses):
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('prior\n')
            with self.assertRaisesRegex(ValueError, 'Incomplete folder'):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'prior\n')

    def test_repeating_pagination_fails(self):
        adapter = self.adapter()
        with patch.object(adapter, '_fetch', return_value=(ajax(doc(1)), SOURCE)):
            with self.assertRaisesRegex(ValueError, 'Pagination repeated'):
                adapter._entries(None, page(doc(1), more=True), SOURCE)

    def test_rejects_missing_inventory_foreign_links_and_unknown_entries(self):
        for text in ('<html>Unavailable</html>', page('<a class="gIconLink" href="https://elsewhere.es/x.pdf">Plano</a>')):
            with self.assertRaises(ValueError):
                parse_page(text, SOURCE)
        adapter = self.adapter()
        for title in ('Modelo de solicitud de licencia', 'Licitación obras', 'Fiestas patronales'):
            with patch.object(adapter, '_fetch', return_value=(page(doc(1, title)), SOURCE)):
                with self.assertRaisesRegex(ValueError, 'Unreviewed planning entry'):
                    adapter.backfill_proyectos(Path('unused.jsonl'))

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = self.adapter().backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
