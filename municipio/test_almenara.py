import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.almenara import (AlmenaraAyuntamientoAdapter, INDEX, SOURCE,
                                         parse_inventory, parse_project)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    names = [INDEX, '01_TC_Documento_de_sintesis.pdf', '03_TC_Ordenanzas_de_las_NNSS.pdf',
             '04_Ordenanzas_del_Planeamiento_de_Desarrollo.pdf', 'P01a_Clasificacion.pdf']
    return ('<h1 id="indextitle">Index of /auto/12011 Almenara</h1><table id="indexlist">' +
            ''.join(f'<tr><td class="indexcolname"><a href="{n}">{n}</a></td></tr>' for n in names * 2) +
            '</table>' + extra)


TEXT = ('Texto Consolidado de planeamiento urbanístico\nde Almenara\nOctubre de 2023\n'
        'Según informe técnico de fecha 22 de junio de 2023. Fecha: 2023.11.13\n'
        'Este documento tiene carácter informativo y no tiene valor jurídico.\n'
        'ÍNDICE DE DOCUMENTOS QUE COMPONEN EL TEXTO CONSOLIDADO')


class AlmenaraTests(unittest.TestCase):
    def test_group_documents_and_preserve_date_semantics(self):
        row = parse_project(parse_inventory(inventory()), TEXT)
        self.assertEqual(len(row['documentos']), 5)
        self.assertTrue(all(d['url'].startswith(SOURCE) for d in row['documentos']))
        self.assertEqual(row['codigo_ine'], '12011')
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_reject_forms_other_municipality_and_incomplete_directory(self):
        for html in ['<h1>Solicitud de licencia</h1>', inventory().replace('12011 Almenara', '25021 Almenar'),
                     inventory().replace(INDEX, 'licencia.pdf')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_project(parse_inventory(inventory()), 'Anuncio de licitación de redacción del texto')

    def test_pagination_and_new_subdirectories_fail_loudly(self):
        for extra in ['<a href="?page=2" rel="next">2</a>', '<a href="2">Siguiente</a>',
                      '<table id="indexlist"><td class="indexcolname"><a href="nuevo/">nuevo</a></td></table>']:
            with self.assertRaises(ValueError):
                parse_inventory(inventory(extra))

    def test_failed_refresh_preserves_previous_snapshot(self):
        adapter = AlmenaraAyuntamientoAdapter('almenara')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', return_value=b'<html>Login</html>'):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_resolves_and_licences_disabled(self):
        manifest = load_manifest('almenara')
        self.assertEqual(manifest.provincia, 'Castellón')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
