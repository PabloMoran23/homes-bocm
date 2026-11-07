"""Offline contract tests for Punta Umbría's HTML and Wicket inventories."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.punta_umbria import (
    SOURCE, PuntaUmbriaAyuntamientoAdapter, make_record, parse_page,
)
from municipio.manifest import load_manifest, load_yaml

BASE = 'https://umbria.sedelectronica.es/transparency/11111111-1111-1111-1111-111111111111/'
DOC = 'https://umbria.sedelectronica.es/preview-document/'


def document(number, title='Estudio de Detalle', description=''):
    return (f'<tr><td><a class="gIconLink" href="{DOC}{number:08}-1111-1111-1111-111111111111" '
            f'title="{description}">{title}</a></td></tr>')


def folder(title, count):
    return (f'<tr><td><a class="gIconLink exp" href="#" '
            f'''onclick="wicketAjaxGet('../../?x=folder')">{title}<span> ( {count} )</span></a></td></tr>''')


MORE = '''<button onclick="wicketAjaxGet('../../?x=more')">Mostrar más</button>'''


class PuntaUmbriaTests(unittest.TestCase):
    def setUp(self):
        self.adapter = PuntaUmbriaAyuntamientoAdapter('punta-umbria')

    def test_html_metadata_and_folder_count(self):
        entries, more = parse_page('<table>' + folder('ESTUDIO DE DETALLE CALLE LEPANTO', 13)
                                   + document(1, 'Decreto', 'Descripción original') + '</table>' + MORE, BASE)
        self.assertEqual(entries[0]['count'], 13)
        self.assertEqual(entries[0]['titulo'], 'ESTUDIO DE DETALLE CALLE LEPANTO')
        self.assertEqual(entries[1]['descripcion_fuente'], 'Descripción original')
        self.assertEqual(more, 'https://umbria.sedelectronica.es/?x=more')

    def test_xml_pagination_and_stable_provenance(self):
        first = '<table>' + document(1) + '</table>' + MORE
        second = ('<?xml version="1.0"?><ajax-response><component id="row"><![CDATA['
                  + document(2) + ']]></component><component id="more"><![CDATA['
                  '<div style="display:none"></div>]]></component></ajax-response>')
        with patch.object(self.adapter, '_get', side_effect=[(first, BASE), (second, 'https://umbria.sedelectronica.es/?x=more')]):
            entries, canonical = self.adapter._inventory(None, BASE)
        self.assertEqual(len(entries), 2)
        self.assertEqual(canonical, BASE)
        self.assertEqual(entries[1]['inventory_url'], BASE)

    def test_repeated_pagination_fails(self):
        html = '<table>' + document(1) + '</table>' + MORE
        with patch.object(self.adapter, '_get', return_value=(html, BASE)):
            with self.assertRaisesRegex(ValueError, 'repeated'):
                self.adapter._inventory(None, BASE)

    def test_invalid_source_or_empty_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_page('<td><a class="gIconLink" href="https://example.org/doc">Plan</a></td>', BASE)
        with patch.object(self.adapter, '_get', return_value=('<html>Login</html>', BASE)):
            with self.assertRaises(ValueError):
                self.adapter._inventory(None, BASE)
        with self.assertRaises(ValueError):
            parse_page('<?xml version="1.0"?><ajax-response/>', BASE)

    def test_grouping_exclusions_and_dates(self):
        root = ('<table>' + folder('ESTUDIO DE DETALLE CALLE LEPANTO', 2)
                + document(3, 'ANUNCIO APROBACIÓN INICIAL MODIFICACIÓN PUNTUAL 16')
                + document(4, 'Acuerdo', 'APROBACIÓN INICIAL MODIFICACIÓN PUNTUAL Nº 16 PGOU')
                + document(5, 'Planos', 'Servicios de Temporada de Playas 2023') + '</table>')
        docs = '<table>' + document(1, 'Estudio') + document(2, 'Anuncio BOP 23-6-2026') + '</table>'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rows.jsonl'
            with patch.object(self.adapter, '_get', side_effect=[(root, SOURCE), (docs, BASE)]):
                result = self.adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(result['count'], 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual({d['titulo'] for d in rows[0]['documentos']}, {'Estudio', 'Anuncio BOP 23-6-2026'})
        for row in rows:
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '21060')
            for invented in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertNotIn(invented, row)

    def test_incomplete_folder_does_not_replace_output(self):
        root = '<table>' + folder('ESTUDIO DE DETALLE CALLE LEPANTO', 13) + '</table>'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rows.jsonl'
            output.write_text('previous snapshot')
            with patch.object(self.adapter, '_get', side_effect=[(root, SOURCE), ('<table>' + document(1) + '</table>', BASE)]):
                with self.assertRaisesRegex(ValueError, 'count mismatch'):
                    self.adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_unknown_material_is_not_silently_included(self):
        for content in [document(1, 'Solicitud de licencia'), folder('LICITACIONES', 1)]:
            with patch.object(self.adapter, '_get', return_value=('<table>' + content + '</table>', SOURCE)):
                with self.assertRaisesRegex(ValueError, 'Unreviewed'):
                    self.adapter.backfill_proyectos(Path('/unused'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('punta-umbria')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('21060', 'Punta Umbría', 'Huelva'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertTrue(self.adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
