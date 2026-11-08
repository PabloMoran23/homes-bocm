import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.abanto_y_ciervana_abanto_zierbena import (
    AbantoZierbenaAyuntamientoAdapter as Adapter, SOURCE,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


class AbantoParserTests(unittest.TestCase):
    def inventory(self, links):
        return '<div class="slm-layout-main"><div class="link-item">' + links + '</div></div>'

    def test_inventory_dedup_exclusions_and_new_instrument_discovery(self):
        link = '<a href="nuevo.aspx">Estudio de Detalle nuevo</a>'
        html = self.inventory(link + link + '<a href="PGOU.aspx">Plan General de Ordenación Urbana</a>'
                              + '<a href="consejo.pdf">Reglamento municipal del consejo</a>')
        entries, excluded = Adapter.parse_inventory(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(excluded), 2)
        self.assertTrue(entries[0]['url'].endswith('/nuevo.aspx'))

    def test_pagination_and_changed_inventory_fail_closed(self):
        for paging in ('<a href="?Page=2">2</a>', '<a rel="next" href="p2">Más</a>',
                       '<a href="p2" title="Siguiente página">→</a>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(self.inventory('<a href="p.aspx">Plan especial</a>') + paging)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<html>Unavailable</html>')
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            Adapter.parse_inventory(self.inventory('<a href="form.aspx">Solicitud de licencia</a>'))

    def test_group_documents_and_separate_agreements_from_filename_dates(self):
        entry = {'titulo': 'Estudio de Detalle', 'url': SOURCE.replace('Planificacionurbanistica', 'detalle')}
        html = '''<div id="MainContent"><p>Mediante acuerdo de fecha 25 de septiembre de 2025,
        se aprobó inicialmente el Estudio de Detalle.</p>
        <p>Mediante acuerdo de Pleno, de fecha 27 de noviembre de 2025,
        fue aprobado definitivamente el Estudio de Detalle.</p>
        <a href="/planes/20260102-inicial.pdf">Proyecto inicial</a>
        <a href="/planes/final.pdf">Texto definitivo</a>
        <a href="/planes/final.pdf">Duplicado</a></div>'''
        row = Adapter.parse_detail(html, entry)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['acuerdos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2025-11-27')
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['documentos'][0]['source_url'], entry['url'])
        self.assertEqual(row['id'], Adapter.parse_detail(html, entry)['id'])

    def test_ambiguous_dates_remain_in_narrative_and_missing_docs_explicit(self):
        entry = {'titulo': 'Estudio de detalle San Miguel', 'url': SOURCE}
        text = ('En sesión de 25 de marzo de 2021 se adoptó el acuerdo de aprobación definitiva. '
                'El anuncio se publicó el 2 de abril de 2021.')
        row = Adapter.parse_detail('<div id="MainContent"><p>' + text + '</p></div>', entry)
        self.assertEqual(row['documentos_status'], 'not_exposed')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIn(text, row['descripcion'])
        with self.assertRaises(ValueError):
            Adapter.parse_detail('<div id="MainContent">Solicitud de licencia</div>', entry)
        with self.assertRaises(ValueError):
            Adapter.parse_detail('<html>Login</html>', entry)

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('abanto-y-ciervana-abanto-zierbena')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '48002')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')
        with patch.object(Adapter, 'backfill_proyectos', return_value={'rows': 3}) as method:
            self.assertEqual(Adapter(manifest.slug).update_proyectos(Path('unused'), Path('state')), {'rows': 3})
            method.assert_called_once()


if __name__ == '__main__':
    unittest.main()
