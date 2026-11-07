"""Offline regression tests for the public RPGUR HTML contract."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.laviana import (
    DOCS, DETAIL, INVENTORY, ROOT, LavianaAyuntamientoAdapter,
    parse_detail, parse_documents, parse_inventory,
)

BASE = '<base href="' + ROOT + 'pages/tiles/layouts/SimpleLayout.jsp">'


def inventory(ident='2681', start=1, total=1, next_page=False, town='LAVIANA', title='Plan General Ordenación de Laviana - vigente'):
    return BASE + f'''{total} registros encontrados. Mostrando del {start} al {start}
    <table id="instrumento"><tbody><tr>
    <td><a href="../../../action/publico/gestionConsulta?method=retrieve&amp;idInstrumento={ident}">Acceder</a></td>
    <td>Municipal</td><td>{town}</td><td>General</td><td>{title}</td><td>C-0648/09</td><td>Vigente</td>
    </tr></tbody></table>''' + ('''<a href="../../../action/publico/busquedaConsulta?method=listPublico&amp;idConcejo=32&amp;estado=V&amp;ambito=MUN&amp;page=2">Siguiente</a>''' if next_page else '')


def field(name, value):
    return f'<div class="item_row"><label class="label_consulta2">{name} :</label><div class="item_75">{value}</div></div>'


def detail(ident='2681', dates=True):
    return BASE + '<form id="instrumentoForm"><input name="idInstrumento" value="' + ident + '">' + ''.join([
        field('Ámbito', 'Municipal'), field('Concejo', 'LAVIANA'),
        field('Estado', 'Vigente'), field('Denominación', 'Plan General Ordenación de Laviana - vigente'),
        field('Expediente', 'C-0648/09'), field('Notas', 'Texto refundido 14/12/2011; no usar como fecha genérica'),
        field('Enlaces', '<a href="https://sede.asturias.es/bopa/2012/04/19/2012-06611.pdf">TEXTO REFUNDIDO</a>'),
    ]) + (''.join([
        field('acuerdo aprobación definitiva', '26/11/2010'),
        field('publicación BOPA aprobación definitiva', '27/01/2011'),
        field('publicación BOPA Texto Refundido', '<a href="https://sede.asturias.es/bopa/2012/04/19/2012-06611.pdf">19/04/2012</a>'),
    ]) if dates else '') + '</form>'


EMPTY_DOCS = '<h1>Documentos</h1><div id="cuerpo_pagina">No existen Documentos</div>'
DOC_TREE = BASE + '''<h1>Documentos</h1><ul id="menuArbol"><li>NORMATIVA<ul><li>
<a href="../../../action/publico/downloadFileArbolActions?method=descargaDocumentosArbol&amp;idDocumento=6896">Normativa.pdf</a>
</li></ul></li></ul>'''


class LavianaTests(unittest.TestCase):
    def setUp(self):
        self.row = parse_inventory(inventory())[0][0]

    def test_inventory_base_and_missing_dossier(self):
        row = parse_inventory(inventory().replace('C-0648/09', ''))[0][0]
        self.assertEqual(row['url'], DETAIL + '2681')
        self.assertIsNone(row['expediente'])

    def test_count_and_municipality_fail_closed(self):
        for html in [inventory(town='AVILÉS'), inventory(total=2), '<h1>Acceso Bloqueado</h1>', inventory().replace('al 1', 'al 2')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_preserves_filter(self):
        batch, total, start, end, link = parse_inventory(inventory(total=2, next_page=True))
        self.assertEqual((total, start, end, len(batch)), (2, 1, 1, 1))
        self.assertTrue(link.startswith(ROOT + 'action/publico/'))
        with self.assertRaises(ValueError):
            parse_inventory(inventory(total=2, next_page=True).replace('idConcejo=32', 'idConcejo=24'))

    def test_dates_and_grouped_bopa(self):
        row = parse_detail(detail(), self.row)
        self.assertEqual(row['fecha_acuerdo'], '2010-11-26')
        self.assertEqual(row['fecha_publicacion'], '2011-01-27')
        self.assertEqual(row['fecha_publicacion_texto_refundido'], '2012-04-19')
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['documentos'][0]['titulos'], ['TEXTO REFUNDIDO', '19/04/2012'])
        self.assertIsNone(row['geometry'])

    def test_missing_dates_not_inferred_from_notes(self):
        row = parse_detail(detail(dates=False), self.row)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertFalse(row['publication_ready'])

    def test_detail_identity_and_title_validation(self):
        for html in [detail(ident='999'), detail().replace('LAVIANA', 'GIJON'), detail().replace('vigente', 'diferente')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, self.row)

    def test_document_tree_and_empty_vs_blocked(self):
        docs = parse_documents(DOC_TREE, DOCS + '2681')
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['rpgur_document_id'], '6896')
        self.assertTrue(docs[0]['url'].startswith(ROOT + 'action/publico/download'))
        self.assertEqual(parse_documents(EMPTY_DOCS, DOCS + '2681'), [])
        for html in ['Acceso Bloqueado', '<h1>Documentos</h1>']:
            with self.assertRaises(ValueError):
                parse_documents(html, DOCS + '2681')

    def test_complete_refresh_and_convenio_exclusion(self):
        adapter = LavianaAyuntamientoAdapter('laviana')
        def fetch(session, url):
            if url == INVENTORY:
                return inventory(total=2, next_page=True)
            if 'busquedaConsulta' in url:
                return inventory(ident='2523', start=2, total=2, title='Convenio Urbanístico PERI ND-2.2')
            if url == DETAIL + '2681':
                return detail()
            if url == DOCS + '2681':
                return DOC_TREE
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(folder) / 'proyectos.jsonl'
            report = adapter.update_proyectos(out, Path(folder) / 'state.json')
            records = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(report['inventory_records'], 2)
            self.assertEqual(report['rows'], 1)
            self.assertEqual(len(report['excluded']), 1)
            self.assertEqual(len(records[0]['documentos']), 2)
            self.assertEqual(len(report['inventory_pages']), 2)

    def test_paginated_document_tree_is_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            parse_documents(DOC_TREE + '<a href="?page=2">Siguiente</a>', DOCS + '2681')

    def test_unavailable_documents_preserve_verified_instrument(self):
        adapter = LavianaAyuntamientoAdapter('laviana')
        with tempfile.TemporaryDirectory() as folder, patch.object(
            adapter, '_fetch', side_effect=[inventory(), detail(), 'Acceso Bloqueado']
        ):
            path = Path(folder) / 'proyectos.jsonl'
            report = adapter.backfill_proyectos(path)
            row = json.loads(path.read_text())
            self.assertEqual(report['rows'], 1)
            self.assertEqual(report['document_listing_unavailable'], 1)
            self.assertEqual(row['document_listing_status'], 'unavailable')
            self.assertEqual(row['url_documentos'], DOCS + '2681')

    def test_duplicates_do_not_replace_existing_output(self):
        adapter = LavianaAyuntamientoAdapter('laviana')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            pages = [inventory(total=2, next_page=True), inventory(start=2, total=2)]
            with patch.object(adapter, '_fetch', side_effect=pages), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_licences_disabled_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'licencias.jsonl'
            report = LavianaAyuntamientoAdapter('laviana').backfill_licencias(path)
            self.assertEqual(report['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
