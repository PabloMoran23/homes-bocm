"""Deterministic parser and full-snapshot traversal tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.orpesa import (
    OrpesaAyuntamientoAdapter, RESTORATION_FOLDER, ROOT, SOURCE, classify, parse_folder,
)
from municipio.manifest import load_manifest


def folder(*items):
    return '<div class="flip-entries">' + ''.join(
        '<div class="flip-entry"><a href="' + url + '"><div class="flip-entry-title">' + title +
        '</div></a><div class="flip-entry-last-modified">11/6/25</div></div>'
        for title, url in items) + '</div>'


def file_url(identifier):
    return 'https://drive.google.com/file/d/' + identifier + '/view?usp=drive_web&resourcekey=0-public'


class OrpesaTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        for title in ['Modificación PGOU Palmavera.pdf', 'INFORME_AMBIENTAL_PALMAVERA.pdf',
                      'Docum.Inicial.Estrategico-Modificacion Palmavera.pdf']:
            self.assertEqual(classify(title, ROOT)[0], 'mp-palmavera')
        self.assertEqual(classify('MEMORIA EIP del Proyecto de Restauración.pdf', ROOT)[0],
                         classify('ANEJO II EIP_ Fichas Paisaje.pdf', RESTORATION_FOLDER)[0])
        for title in ['Solicitud de obra menor.pdf', 'Ordenanza protección contaminación acústica.pdf',
                      'PROYECTO_DE_MODIFICACION_DE_ORDENANZA_DE_PLAYAS_1.25.pdf',
                      'convenio desaladora acuamed(op).pdf']:
            self.assertIsNone(classify(title, ROOT))
        with self.assertRaises(ValueError):
            classify('Nuevo proyecto de urbanización no revisado.pdf', ROOT)

    def test_parser_preserves_resource_key_and_raw_modified_label(self):
        rows = parse_folder(folder(('Modificación PGOU Palmavera.pdf', file_url('abc'))))
        self.assertEqual(rows[0]['url'], file_url('abc'))
        self.assertEqual(rows[0]['fecha_modificacion_archivo_texto'], '11/6/25')

    def test_missing_content_and_pagination_fail(self):
        for html in ['<h1>Sign in</h1>', '<a href="/es/pgou">PGOU</a>',
                     folder() + '<a rel="next" href="?page=2">Más</a>',
                     folder() + '<div>Siguiente página</div>',
                     folder(*[('x', file_url(str(i))) for i in range(50)]),
                     folder(('X', 'https://unrelated.example/document.pdf'))]:
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                parse_folder(html)

    def test_recursive_snapshot_dates_dedup_and_disabled_licences(self):
        root_url = 'https://drive.google.com/embeddedfolderview?id=' + ROOT
        child_url = 'https://drive.google.com/embeddedfolderview?id=' + RESTORATION_FOLDER
        pages = {
            SOURCE: '<article><iframe src="' + root_url + '"></iframe></article>',
            root_url: folder(
                ('Modificación PGOU Palmavera.pdf', file_url('plan')),
                ('INFORME_AMBIENTAL_PALMAVERA.pdf', file_url('report')),
                ('PROYECTO DE RESTAURACIÓN Parcelas R2C y R14 Torre Bellver.pdf', file_url('restore')),
                ('Solicitud de obra menor.pdf', file_url('form')),
                ('PLAN PARTICIPACION PUBLICA', 'https://drive.google.com/drive/folders/' + RESTORATION_FOLDER)),
            child_url: folder(
                ('PROYECTO DE RESTAURACIÓN Parcelas R2C y R14 Torre Bellver.pdf', file_url('restore')),
                ('ANEJO III EIP_Fotomontajes.pdf', file_url('annex'))),
        }
        adapter = OrpesaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(result['folders_visited'], 2)
            self.assertEqual(len(result['excluded_documents']), 1)
            restore = next(r for r in rows if r['id'].endswith('restauracion-r2c-r14'))
            self.assertEqual(len(restore['documentos']), 2)
            self.assertEqual(len(restore['documentos'][0]['inventarios']), 2)
            for row in rows:
                self.assertEqual(row['codigo_ine'], '12085')
                for key in ('fecha', 'fecha_aprob', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry', 'fase'):
                    self.assertIsNone(row[key])
                self.assertFalse(row['publication_ready'])
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_failure_keeps_previous_snapshot(self):
        adapter = OrpesaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value='<html>Login</html>'):
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest(self):
        manifest = load_manifest('orpesa')
        self.assertEqual(manifest.provincia, 'Castellón')
        self.assertTrue(manifest.proyectos.enabled)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.orpesa:OrpesaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
