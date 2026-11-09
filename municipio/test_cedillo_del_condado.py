"""Offline parser and traversal checks; no live dependency in the tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from municipio.adapters.cedillo_del_condado import (
    HOST, PLAN_TITLE, CedilloDelCondadoAyuntamientoAdapter, ajax_html,
    documents, folders, make_record, more_button,
)


def doc(number, title='MEMORIA INFORMATIVA'):
    return (f'<a href="{HOST}/preview-document/'
            f'00000000-0000-0000-0000-{number:012d}">{title}</a>')


def folder(title, count):
    return (f'<a class="exp" onclick="wicketAjaxGet(\'?x=folder\')">{title}'
            f'<span class="linkExtraInfo"> ( {count} )</span></a>')


MORE = '<button onclick="wicketAjaxGet(\'?x=more\')">Mostrar más</button>'


class CedilloParserTests(unittest.TestCase):
    def test_real_document_links_only_and_deduplication(self):
        html = doc(1) + doc(1) + '<a href="/dossier">Solicitud de Licencia de Obras</a>'
        rows = documents(html, HOST, PLAN_TITLE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values()))['titulo'], 'MEMORIA INFORMATIVA')
        self.assertEqual(documents(doc(1).replace(HOST, 'https://example.org'), HOST, ''), {})

    def test_group_instrument_without_invented_dates(self):
        docs = documents(doc(1) + doc(2, 'PLANO'), HOST, PLAN_TITLE)
        record = make_record(PLAN_TITLE, HOST + '/transparency/plan/', docs)
        self.assertEqual(len(record['documentos']), 2)
        self.assertEqual(record['codigo_ine'], '45047')
        self.assertFalse(record['publication_ready'])
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(record[key])
        self.assertNotIn('fase', record)
        with self.assertRaises(ValueError):
            make_record('Solicitud de licencia', HOST, docs)
        with self.assertRaises(ValueError):
            make_record(PLAN_TITLE, HOST, {})

    def test_folder_count_required(self):
        self.assertEqual(folders(folder('0.1 Memorias', 4))[0][:2], ('0.1 Memorias', 4))
        with self.assertRaises(ValueError):
            folders('<a class="exp" onclick="x">Memorias</a>')

    def test_wicket_components_only(self):
        xml = ('<ajax-response><evaluate>untrusted script</evaluate>'
               '<component><![CDATA[' + doc(2) + MORE + ']]></component></ajax-response>')
        html = ajax_html(xml)
        self.assertNotIn('untrusted', html)
        self.assertEqual(len(documents(html, HOST, '')), 1)
        self.assertIsNotNone(more_button(html))
        with self.assertRaises(ValueError):
            ajax_html('<ajax-response><redirect>/login</redirect></ajax-response>')

    def test_pagination_and_nested_folder_complete(self):
        adapter = CedilloDelCondadoAyuntamientoAdapter()
        adapter._get = Mock(side_effect=[
            SimpleNamespace(text=doc(1) + folder('Memorias', 1) + MORE),
            SimpleNamespace(text=doc(3)),
        ])
        adapter._click = Mock(return_value=SimpleNamespace(text=(
            '<ajax-response><component><![CDATA[' + doc(2) + ']]></component></ajax-response>')))
        adapter._open_folder = Mock(return_value=(HOST + '/child/', 1))
        rows = adapter._crawl(HOST + '/plan/', PLAN_TITLE, 3, set())
        self.assertEqual(len(rows), 3)
        self.assertEqual(adapter._click.call_count, 1)
        self.assertEqual(sum(d['carpeta'].endswith('/Memorias') for d in rows.values()), 1)

    def test_incomplete_inventory_fails(self):
        adapter = CedilloDelCondadoAyuntamientoAdapter()
        adapter._get = Mock(return_value=SimpleNamespace(text=doc(1)))
        with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
            adapter._crawl(HOST, PLAN_TITLE, 2, set())

    def test_stalled_pagination_fails(self):
        adapter = CedilloDelCondadoAyuntamientoAdapter()
        adapter._get = Mock(return_value=SimpleNamespace(text=doc(1) + MORE))
        adapter._click = Mock(return_value=SimpleNamespace(text=(
            '<ajax-response><component><![CDATA[' + doc(1) + MORE + ']]></component></ajax-response>')))
        with self.assertRaisesRegex(ValueError, 'no progress'):
            adapter._crawl(HOST, PLAN_TITLE, 2, set())

    def test_folder_cycle_fails(self):
        adapter = CedilloDelCondadoAyuntamientoAdapter()
        with self.assertRaisesRegex(ValueError, 'cycle'):
            adapter._crawl(HOST, PLAN_TITLE, 1, {HOST})


if __name__ == '__main__':
    unittest.main()
