import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.olvera import INVENTORY_URL, OlveraAyuntamientoAdapter, parse_inventory, register_date
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def row(number, title='UE-6', notes='', approval='26/05/16', publication='BOP: 17/10/16 Nº 197', docs=''):
    return f'''<tr><td><h4>{number}º</h4></td><td>
    1º.- ÁMBITO DE ORDENACIÓN: OLVERA (CÁDIZ).
    2º.- CLASE DE PLANEAMIENTO, FIGURA DE PLANEAMIENTO Y PROCEDIMIENTO: PG PGOU M
    3º.- ÁMBITO CONCRETO DE APLICACIÓN: {title}
    4º.- PROMOTOR: Ayuntamiento de Olvera
    5º.- APROBACIÓN DEFINITIVA: Ayuntamiento {approval}
    6º.- PLAZO DE VIGENCIA: INDEFINIDA</td><td>{publication}</td><td>{notes}</td><td>{docs}</td></tr>'''


def page(rows):
    return '<article class="uk-article"><h1>Instrumentos Urbanísticos</h1><table><tr><td>INSCRIPCIÓN CANCELACIONES</td></tr>' + rows + '</table></article>'


class OlveraTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        docs = '<a href="/one.pdf">Memoria</a><a href="/two.pdf">Plano</a><a href="/one.pdf">Memoria repetida</a>'
        rows, excluded = parse_inventory(page(row(1, docs=docs) + row(2, title='C/ PRUNA', approval='', publication='No consta')))
        self.assertEqual(len(rows), 2)
        self.assertFalse(excluded)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://www.olvera.es/one.pdf')
        self.assertEqual(len(rows[0]['documentos'][0]['titulos']), 2)
        self.assertEqual(rows[0]['fecha_aprob'], '2016-05-26')
        self.assertEqual(rows[0]['fecha_publicacion'], '2016-10-17')
        self.assertNotIn('fecha_aprob', rows[1])
        self.assertNotIn('fecha_publicacion', rows[1])
        self.assertFalse(any(k in rows[0] for k in ('lat', 'lon', 'fase', 'fecha')))

    def test_cancelled_not_emitted(self):
        rows, excluded = parse_inventory(page(row(1) + row(2, notes='ANOTACIÓN DE CANCELACIÓN 27/10/10. No existe planeamiento aprobado.')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(excluded[0]['inscripcion'], 2)

    def test_adaptation_does_not_inherit_1999_approval(self):
        docs = '<a href="/images/Instrumentos_Urbanisticos/NNSS1999/base.PDF">Memoria</a><a href="/images/Instrumentos_Urbanisticos/NNSS_adaptacion_parcial-1/a.PDF">Adaptación parcial</a>'
        rows, _ = parse_inventory(page(row(1, approval='14/12/99', notes='Adaptación Parcial mediante acuerdo Plenario de fecha 18 de mayo de 2010.', docs=docs)))
        adapted, base = rows
        self.assertEqual(adapted['fecha_acuerdo'], '2010-05-18')
        self.assertNotIn('fecha_aprob', adapted)
        self.assertNotIn('fecha_publicacion', adapted)
        self.assertEqual(base['fecha_aprob'], '1999-12-14')
        self.assertEqual(len(base['documentos']), 1)
        self.assertEqual(adapted['relacionado_con'], base['id'])

    def test_fail_closed(self):
        for html in ['<h1>Solicitud de licencia</h1>', page(''), page(row(1) + row(3)), page(row(1) + row(1)), page(row(1)).replace('</article>', '<div class="pagination">2</div></article>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        self.assertIsNone(register_date('31/02/16'))
        self.assertIsNone(register_date('No consta'))

    def test_manifest_and_adapter_io(self):
        manifest = load_manifest('olvera')
        self.assertEqual(manifest.provincia, 'Cádiz')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), OlveraAyuntamientoAdapter)
        response = Mock(url=INVENTORY_URL, text=page(row(1)))
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.olvera.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            adapter = OlveraAyuntamientoAdapter('olvera')
            self.assertEqual(adapter.backfill_proyectos(output)['count'], 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '11024')
            self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state.json')['count'], 1)
            self.assertEqual(adapter.backfill_licencias(output)['count'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
