import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vimianzo import SOURCE, VimianzoAyuntamientoAdapter
from municipio.manifest import load_manifest

TITLE = 'MODIFICACIÓN PUNTUAL 5 DAS NNSS DE VIMIANZO'
URL = 'https://www.vimianzo.gal/info.php?id=483&idioma=gl&sec=311'


def detail(body, title=TITLE):
    return f'<div id="CONTIDOS"><h1 class="titSeccion">{title}</h1><div class="contido">{body}</div></div>'


def inventory(number=5, item_id=483, pages=''):
    return ('<div id="CONTIDOS"><h1 class="titSeccion">Normativa</h1>'
            f'<div class="listado"><a class="tit" href="?sec=311&id={item_id}">'
            f'MODIFICACIÓN PUNTUAL {number} DAS NNSS DE VIMIANZO</a></div></div>' + pages)


class VimianzoTests(unittest.TestCase):
    def test_group_documents_and_separate_publication(self):
        body = ('<li><a href="http://bop.dicoruna.es/2018.pdf">Aprobación definitiva da '
                'MODIFICACIÓN PUNTUAL 5 (MP5), publicada no BOP NÚM. 220, do 19/11/2018.</a></li>'
                '<li><a href="../media/documentos/MP5_NNSS.pdf">Documento MP5</a> '
                'Documento aprobado provisionalmente polo Pleno o 16 de marzo de 2018, '
                'pendente de aprobación definitiva pola Xunta de Galicia.</li>')
        row = VimianzoAyuntamientoAdapter.parse_detail(detail(body), URL, TITLE)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertEqual(row['fecha_publicacion'], '2018-11-19')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['geometry'])
        self.assertIn('16 de marzo de 2018', row['documentos'][1]['contexto_fuente'])
        self.assertEqual(row['documentos'][1]['url'], 'https://www.vimianzo.gal/media/documentos/MP5_NNSS.pdf')

    def test_undated_document_is_not_approval(self):
        row = VimianzoAyuntamientoAdapter.parse_detail(
            detail('<a href="media/documentos/plan.pdf">MEMORIA</a>'), URL, TITLE)
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertFalse(row['publication_ready'])

    def test_reject_navigation_missing_documents_and_wrong_instrument(self):
        for html in ['<h1>Login</h1>', detail('<p>Formulario de licenza</p>'),
                     detail('<a href="plan.pdf">Plan</a>', 'Otra noticia')]:
            with self.assertRaises(ValueError):
                VimianzoAyuntamientoAdapter.parse_detail(html, URL, TITLE)
        with self.assertRaises(ValueError):
            VimianzoAyuntamientoAdapter.parse_inventory('<a href="?id=483&sec=311">Plan</a>')

    def test_inventory_excludes_generic_downloads(self):
        html = inventory() + '<div id="other"><a href="?sec=311&id=999">Licencias</a></div>'
        items, pages = VimianzoAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(list(items), [URL])
        self.assertEqual(pages, set())

    def test_crawls_discovered_pagination_and_refreshes(self):
        first = inventory(pages='<a href="?sec=311&page=2">Seguinte</a>')
        second = inventory(6, 484, '<a href="?sec=311&page=1">Anterior</a>')
        pages = {SOURCE + '&page=1': first, SOURCE + '&page=2': second,
                 URL: detail('<a href="plan.pdf">MP5</a>'),
                 URL.replace('483', '484'): detail('<a href="plan6.pdf">MP6</a>', TITLE.replace('5', '6'))}
        adapter = VimianzoAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            output = Path(directory) / 'records.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)

    def test_repeated_page_fails_without_overwriting_output(self):
        adapter = VimianzoAyuntamientoAdapter()
        html = inventory(pages='<a href="?sec=311&page=2">Seguinte</a>')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', return_value=html):
            output = Path(directory) / 'records.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('vimianzo')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = VimianzoAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
