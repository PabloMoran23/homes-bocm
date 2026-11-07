"""Offline source-shaped fixtures; live evidence is intentionally not a fixture."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.haro import HaroAyuntamientoAdapter as Adapter, INVENTORY, CATALOG
from municipio.adapters.haro import instrument_key, labelled_date
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def detail(title, description, links=''):
    return f'<div id="page"><h3>{title}</h3><div class="pi-box"><p>{description}</p></div><div class="pi-tab-pane">{links}</div></div>'


def inventory(entries):
    return ''.join(f'<div class="pi-box"><h4>{title}</h4><a href="/es/ayuntamiento/urbanismo/{number}">Ver detalles</a></div>' for number, title in entries)


class HaroParserTests(unittest.TestCase):
    def test_inventory_scope_and_deduplication(self):
        html = inventory([(41, 'Aprobación definitiva 31ª modificación del PGM'),
                          (41, 'Aprobación definitiva 31ª modificación del PGM'),
                          (2, 'Avance Plan General 2013. Revisión, modificación y adaptación'),
                          (1, 'Plan General Municipal de Haro 2013. Revisión, modificación'),
                          (34, 'CONVENIOS URBANÍSTICOS')])
        selected, excluded = Adapter.parse_inventory(html)
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(excluded), 3)

    def test_pagination_and_markup_fail_closed(self):
        html = inventory([(39, 'Plan Parcial del Sector 5')])
        for extra in ['<a rel="next" href="?page=2">Más</a>',
                      '<div class="pagination"><a href="?page=2">2</a></div>',
                      '<a href="?page=2">Siguiente</a>', '<a href="/pagina/2">»</a>']:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html + extra)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<h1>Unavailable</h1>')
        with self.assertRaises(ValueError):
            Adapter.parse_detail('<h1>Login</h1>', CATALOG)

    def test_explicit_dates_and_unknown_dates(self):
        parsed = Adapter.parse_detail(detail('10ª modificación del PEPCHA',
            'APROBACIÓN INICIAL: 10 de abril de 2024 APROBACIÓN DEFINITIVA: 18 de diciembre de 2024 PUBLICACIÓN EN EL BOR: 27 de enero de 2025'), CATALOG)
        self.assertEqual(parsed['fecha_aprob'], '2024-12-18')
        self.assertEqual(parsed['fecha_publicacion'], '2025-01-27')
        self.assertEqual(labelled_date('APROBACIÓN DEFINITIVA POR LA COTUR 29 DE ABRIL DE 2016', r'aprobacion definitiva'), '2016-04-29')
        self.assertEqual(labelled_date('BOR: 23/12/2019', 'bor'), '2019-12-23')
        cotur = Adapter.parse_detail(detail('9ª modificación PGM', 'APROBACIÓN DEFINITIVA COTUR: 4 MAYO 2007 BOR: 19 DE MAYO DE 2007'), CATALOG)
        self.assertEqual(cotur['fecha_aprob'], '2007-05-04')
        typo = Adapter.parse_detail(detail('23ª modificación PGM', 'APROBACIÓN DEFINTIVA COTUR 31 OCTUBRE 2013'), CATALOG)
        self.assertEqual(typo['fase'], 'aprobación definitiva')
        unknown = Adapter.parse_detail(detail('Plan Parcial del Sector 5', 'Documento aprobado. Año 2024'), CATALOG)
        self.assertIsNone(unknown['fecha_aprob'])
        self.assertIsNone(unknown['fecha_publicacion'])

    def test_group_stages_and_retain_document_provenance(self):
        url = 'https://www.haro.org/es/ayuntamiento/urbanismo/'
        initial = Adapter.parse_detail(detail('Aprobación inicial 31ª Modificación Puntual PGM', 'Aprobación inicial'), url+'40')
        final = Adapter.parse_detail(detail('Aprobación definitiva 31ª modificación del PGM', 'Aprobación definitiva',
            '<a href="/descargas/textos-planos/94">Documento</a><a href="/descargas/textos-planos/94">Duplicado</a>'), url+'41')
        catalog = [{'titulo': '31ª modificación PGM', 'url': 'https://www.haro.org/descargas/textos-planos/95', 'source_url': CATALOG}]
        rows = Adapter.group_details([initial, final], catalog)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['id'], 'haro-proy-pgm-mod-31')
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertEqual(len(row['fuentes']), 2)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], url+'41')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])
        self.assertNotEqual(instrument_key('10ª modificación del PEPCHA', url+'43'), instrument_key('10ª modificación PGM', url+'20'))

    def test_manifest_resolution_and_snapshot_update(self):
        manifest = load_manifest('haro')
        adapter = load_portal_adapter(manifest)
        self.assertEqual(manifest.provincia, 'La Rioja')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 34}) as backfill:
                self.assertEqual(adapter.update_proyectos(path, Path(directory)/'state.json')['rows'], 34)
                backfill.assert_called_once_with(path)
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
