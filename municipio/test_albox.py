"""Offline parser tests: run with python -m unittest municipio.test_albox."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.albox import AlboxAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def link(filename, label=None):
    return f'<a href="https://www.dipalme.org/Servicios/Anexos/Anexos.nsf/TEST/$file/{filename}">{label or filename}</a>'


def inventory(body):
    return '<div id="content"><h1>Urbanismo</h1><div class="limpiar_fondo">' + body + '</div></div>'


class AlboxTests(unittest.TestCase):
    def test_grouping_duplicates_and_dates(self):
        html = inventory(link('ESTUDIO SECTOR 7 y 8.pdf') + link('Ficha_Justificativa_Decreto_293_2009.pdf') +
                         link('CERT_APROBA.DEFIN. ESTUDIO DETALLE_SECTORES 7 y 8.pdf') +
                         link('MEMORIA_APL_PGOU_08.pdf') * 2 + link('03_ORDENACION-TERMINO-MUNICIPAL.pdf'))
        rows = AlboxAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2])
        self.assertEqual(len({r['id'] for r in rows}), 2)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '04006')
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'fase', 'lat', 'lon'):
                self.assertIsNone(row[field])

    def test_distinct_normative_instruments_and_maps(self):
        rows = AlboxAyuntamientoAdapter.parse_inventory(inventory(
            link('MOD-NORMAS_AP-DEFINITIVA.pdf') + link('ORDENANZA_DEFINITIVA_NO URBANIZABLE.pdf') +
            link('Alineaciones Pueblo.pdf') + link('Alturas Pueblo.pdf') +
            link('ESTUDIO DETALLE AVDA. LEPANTO.PDF') + link('CERT_ LEPANTO.pdf') +
            link('BOP._APROB. DEFINI. MODIF_PGOU_PLAZA MAYOR.pdf', 'Modificación Plaza Mayor')))
        self.assertEqual(len(rows), 5)
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [1, 1, 1, 2, 2])

    def test_fail_closed(self):
        for html in ('<h1>Login</h1>', inventory('<p>Formulario de licencia</p>'),
                     inventory(link('nueva-modificacion.pdf')),
                     inventory(link('MOD-NORMAS_AP-DEFINITIVA.pdf') + '<a rel="next" href="?page=2">2</a>'),
                     inventory(link('MOD-NORMAS_AP-DEFINITIVA.pdf') + '<a href="?offset=20">Más</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                AlboxAyuntamientoAdapter.parse_inventory(html)

    def test_manifest_live_interface(self):
        manifest = load_manifest('albox')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(text=inventory(link('MEMORIA_APL_PGOU_08.pdf')))
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.albox.requests.get', return_value=response) as get:
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertTrue(output.read_text())
            self.assertEqual(get.call_args.args[0], SOURCE)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
