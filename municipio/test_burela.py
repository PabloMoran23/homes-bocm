import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.burela import (
    BurelaAyuntamientoAdapter, SOURCE, parse_instrument, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def page(title, body):
    return f'<article><h1>{title}</h1><div class="field-name-body">{body}</div></article>'


INVENTORY = page('Urbanismo', '''
<a href="/gl/node/68">Documento de Aprobación Definitiva</a>
<a href="/es/node/999">Aprobación Inicial de la Modificación Puntual del PXOM</a>
<a href="/form.pdf">Solicitud de licencia de obra</a>''')
DEFINITIVE = page('PXOM: Documento de Aprobación Definitiva', '''
<p>O Plan Xeral de Ordenación Municipal de Burela foi aprobado definitivamente segundo
Orde de 31 de marzo de 2014, publicada no D.O.G. número 64, de 2 de abril de 2014,
e publicadas as Normas no B.O.P. número 086, de 14 de abril de 2014.</p>
<a href="http://www.burela.org/PXOM/Memoria xeral.pdf">Memoria</a>
<a href="/PXOM/Memoria%20xeral.pdf"><img src="icon.png"></a>
<a href="/PXOM/Normas.pdf">Normas</a>''')
INITIAL = page('Aprobación Inicial de la Modificación Puntual del PXOM', '''
<p>Documentación correspondente ao período de información pública.</p>
<ul><li>01.MX - <a href="/PXOM22/01.MX.zip">Descargar</a></li></ul>''')


class BurelaTests(unittest.TestCase):
    def test_inventory_excludes_licence_form(self):
        self.assertEqual(parse_inventory(INVENTORY), {
            'pxom': 'https://burela.org/gl/node/68',
            'modificacion': 'https://burela.org/es/node/999',
        })

    def test_groups_documents_and_distinguishes_dates(self):
        row = parse_instrument(DEFINITIVE, SOURCE, 'pxom')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['titulos_fuente'], ['Memoria'])
        self.assertIn('%20', row['documentos'][0]['url'])
        self.assertEqual(row['fecha_aprob'], '2014-03-31')
        self.assertEqual(row['fecha_publicacion'], '2014-04-02')
        self.assertEqual(row['fecha_publicacion_normativa'], '2014-04-14')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])

    def test_initial_has_no_invented_dates(self):
        row = parse_instrument(INITIAL, SOURCE, 'modificacion')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['documentos'][0]['titulos_fuente'], ['01.MX - Descargar'])

    def test_pagination_and_missing_sources_fail(self):
        for html in [INVENTORY + '<a rel="next" href="?page=1">More</a>',
                     INVENTORY + '<ul class="pager"><li>2</li></ul>',
                     page('Urbanismo', '<p>Servicios y formularios</p>')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_instrument(INITIAL.replace('/PXOM22/01.MX.zip', '/form'), SOURCE, 'modificacion')

    def test_partial_fetch_does_not_replace_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with patch('municipio.adapters.burela.requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    BurelaAyuntamientoAdapter('burela').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('burela')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, BurelaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
