import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.muskiz import MuskizAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def section(title, body):
    return f'<div><div><h3 class="ms-WPTitle">{title}</h3></div><div class="ms-WPBody">{body}</div></div>'


def inventory():
    return ''.join([
        section('Normas subsidiarias', '<a href="/docs/nnss1993.pdf">Normas Subsidiarias</a>'),
        section('Modificaciones Normas Subsidiarias', '<a href="/docs/ies.pdf">Aprobación definitiva, si procede, IES (19 de abril 2016)</a>'),
        section('Plan General de Ordenación Urbana (P.G.O.U.)', '''
            <ul><li><a href="/docs/alcance.pdf">Documento de alcance</a>
            <p>Fecha de publicación en la web: 05/11/2026.</p></li>
            <li><a href="/docs/alcance.pdf">Duplicado</a></li>
            <li><a href="/docs/vocal.pdf">Nombramiento de vocales</a></li>
            <li><a href="https://bit.ly/avance">Avance III Octubre 2024</a></li></ul>'''),
        section('Documentación', '<a href="/docs/fase1.pdf">Fase I</a>'),
        section('Plan especial para la construcción de un centro de adiestramiento de perros y hotel canino en la parcela 704 del polígono 01 de Muskiz (Publicado 10/07/2025)', '<a href="/docs/canino.pdf">Plan especial</a>'),
        section('Noticias', '<a href="/noticia">Formulario licencia</a>'),
    ])


class MuskizTests(unittest.TestCase):
    def test_instruments_grouped_with_provenance_and_date_semantics(self):
        rows = MuskizAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 4)
        pgou = rows[2]
        self.assertEqual(len(pgou['documentos']), 3)
        self.assertEqual(pgou['documentos'][0]['fecha_publicacion'], '2026-11-05')
        self.assertEqual(pgou['documentos'][0]['url_procedencia'], SOURCE)
        self.assertIsNone(pgou['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])  # filename year is not approval
        self.assertIsNone(rows[1]['fecha_aprob'])  # conditional agenda title
        self.assertEqual(rows[3]['fecha_publicacion'], '2025-07-10')
        self.assertTrue(all(r['geometry'] is None and r['codigo_ine'] == '48071' for r in rows))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in MuskizAyuntamientoAdapter.parse_projects(inventory())])

    def test_pagination_rejected_without_truncation(self):
        for extra in ['<a href="?page=2">Siguiente</a>', '<a href="?p=2" rel="next">2</a>', '<div class="pagination">2</div>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                MuskizAyuntamientoAdapter.parse_projects(inventory() + extra)

    def test_source_loss_and_new_ungrouped_modification_rejected(self):
        for html in ['', inventory().replace('Normas subsidiarias', 'Missing', 1), inventory().replace('/docs/canino.pdf', 'https://external.example/canino.pdf'), inventory().replace('Aprobación definitiva, si procede, IES', 'Otra modificación')]:
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                MuskizAyuntamientoAdapter.parse_projects(html)

    def test_live_entrypoint_refresh_and_disabled_licences(self):
        response = Mock(text=inventory(), url=SOURCE)
        adapter = MuskizAyuntamientoAdapter('muskiz')
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.muskiz.requests.get', return_value=response):
            out = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['rows'], 4)
            self.assertEqual(len([json.loads(x) for x in out.read_text().splitlines()]), 4)
            self.assertEqual(adapter.update_licencias(out, None)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
            out.write_text('previous successful output')
            response.text = '<html>changed source</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous successful output')

    def test_manifest_contract_and_loading(self):
        manifest = load_manifest('muskiz')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('48071', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), MuskizAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
