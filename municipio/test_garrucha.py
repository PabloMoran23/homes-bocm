"""Offline parser and traversal contract tests; no network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from municipio.adapters.garrucha import (
    INVENTORIES, GarruchaAyuntamientoAdapter, expansion,
    parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest

IDENT = 'CEF33FBCE5CA6CD3C125811700263E3B'
TITLE = 'ESTUDIO DE DETALLE RESIDENCIAL ALDEA MARINA BOP Nº 84 DE 05.05.2017'
LINK = f'<a href="/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Garrucha&amp;documentId={IDENT}">{TITLE}</a>'
PANEL = '<div id="cmsdip-pro-tablon-view1">{}</div>'
ATTACHMENT = '/Servicios/Tablon/anexos.nsf/ED483C04E7E2B7D7C125811700268C89/$file/estudio.pdf'
DETAIL = f'''<div id="doc-dipalme-titulo"><h1>{TITLE}</h1></div>
<h2>Ayuntamiento de Garrucha</h2><p>Normas - Planeamiento Urbanístico</p>
<div>Publicado: <strong>05/05/2017</strong></div>
<div id="view:_id11:fanuncio_Texto1">APROBACION DEFINITIVA ESTUDIO DE DETALLE</div>
<table id="attachments"><tr><td><a href="{ATTACHMENT}" title="estudio.pdf">estudio.pdf</a></td>
<td><a href="{ATTACHMENT}">[descargar]</a></td></tr></table>'''


def tree(title, position):
    return (PANEL.format(f'<button id="view:panel:0:col__expand:{position}button" title="plegado {title}"></button>') +
            '<form class="xspForm"><input name="$$viewid" value="state"/><input name="$$xspsubmitid"/></form>')


class GarruchaTests(unittest.TestCase):
    def test_grouping_dates_and_identity(self):
        rows = parse_inventory(PANEL.format(LINK * 2 + '<a href="/form">Solicitud de licencia</a>'), INVENTORIES[0])
        self.assertEqual(len(rows), 1)
        row = parse_detail(DETAIL, rows[0])
        self.assertEqual(row['codigo_ine'], '04049')
        self.assertEqual(row['fecha_publicacion'], '2017-05-05')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertNotIn('fecha', row)
        self.assertNotIn('lat', row)
        self.assertEqual(row['fase'], 'aprobacion_definitiva')
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['documentos'][0]['source_url'], row['url'])

    def test_advance_is_not_approval(self):
        title = 'AVANCE PLAN GENERAL ORDENACION URBANA DE GARRUCHA'
        row = parse_inventory(PANEL.format(LINK.replace(TITLE, title)), INVENTORIES[1])[0]
        result = parse_detail(DETAIL.replace(TITLE, title).replace('APROBACION DEFINITIVA ESTUDIO DE DETALLE', title), row)
        self.assertEqual(result['fase'], 'avance')
        self.assertIsNone(result['fecha_aprob'])

    def test_fail_on_pagination_or_missing_content(self):
        for control in ['<a href="?page=2">Siguiente</a>', '<a class="xspPagerNav" href="#">2</a>',
                        '<a rel="next" href="?page=2">→</a>', '<td class="xspDataTableViewPanelFooterMiddle"><a id="pager">2</a></td>']:
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(PANEL.format(LINK + control), INVENTORIES[0])
        with self.assertRaises(ValueError):
            parse_inventory('<html/>', INVENTORIES[0])
        row = parse_inventory(PANEL.format(LINK), INVENTORIES[0])[0]
        for html in [DETAIL.replace('id="attachments"', 'id="lost"'), DETAIL.replace(TITLE, 'Other'),
                     DETAIL.replace('Publicado:', 'Fecha:')]:
            with self.assertRaises(ValueError):
                parse_detail(html, row)

    def test_external_and_wrong_municipality_rejected(self):
        for link in [LINK.replace('/Servicios/', 'https://example.org/Servicios/'), LINK.replace('p=Garrucha', 'p=Vera')]:
            with self.assertRaises(ValueError):
                parse_inventory(PANEL.format(link), INVENTORIES[0])
        row = parse_inventory(PANEL.format(LINK), INVENTORIES[0])[0]
        with self.assertRaises(ValueError):
            parse_detail(DETAIL.replace(ATTACHMENT, 'https://example.org/file.pdf'), row)

    def test_category_subtree_traversal(self):
        first = tree('Planeamiento Urbanístico', '418.4')
        second = tree('Registro de Instrumentos de Planeamiento', '418.4.1')
        self.assertIsNone(expansion(tree('Ordenanzas', '418.2'), None))
        self.assertIsNone(expansion(tree('Reglamentos', '418.5'), '418.4'))
        def response(html):
            return Mock(url=INVENTORIES[0], text=html)
        session = Mock()
        session.get.return_value = response(first)
        session.post.side_effect = [response(second), response(PANEL.format(LINK))]
        adapter = GarruchaAyuntamientoAdapter('garrucha')
        rows = adapter._inventory(session, INVENTORIES[0], 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(session.post.call_args_list[1].kwargs['data']['$$xspsubmitid'],
                         'view:panel:0:col__expand:418.4.1')
        session.post.side_effect = [response(second), response(second)]
        with self.assertRaisesRegex(ValueError, 'did not advance'):
            adapter._inventory(session, INVENTORIES[0], 0)

    def test_disabled_licences_and_manifest(self):
        manifest = load_manifest('garrucha')
        self.assertEqual(manifest.provincia, 'Almería')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = GarruchaAyuntamientoAdapter('garrucha').backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
