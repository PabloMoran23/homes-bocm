import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.benetusser import BenetusserAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def block(title, links):
    return ('<div class="toggle"><h3 class="toggle-title">' + title + '</h3>'
            '<div class="inner-toggle-wrap">' + ''.join(
                f'<a href="{url}">{label}</a>' for label, url in links) + '</div></div>')


def catalogue():
    return ''.join(block(title, [('Descargar documento', f'/files/{key}.pdf')]) for key, title in [
        ('agenda', 'Agenda Urbana de Reconstrucción de Benetússer Post-DANA 2024'),
        ('pgou', 'PGOU Plan General de Ordenación Urbana (1990)'),
        ('puam', 'PUAM Plan Urbano de Actuación Municipal 2022'),
        ('emus', 'EMUS Programa de movilidad urbana sostenible 2018'),
    ])


class BenetusserTests(unittest.TestCase):
    def test_real_instruments_only_and_no_invented_dates_or_geometry(self):
        html = catalogue() + block('Solicitud de licencia de obra', [('Formulario', '/solicitud.pdf')])
        html += block('II Plan de Igualdad Ayuntamiento de Benetússer', [('Plan', '/igualdad.pdf')])
        html += block('Licitación de obras', [('Anuncio', '/contrato.pdf')])
        rows = BenetusserAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '46054')
            self.assertEqual(row['url'], SOURCE)
            for name in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[name])
            self.assertFalse(row['publication_ready'])

    def test_group_documents_and_repeated_instruments_without_losing_links(self):
        html = catalogue() + block('PGOU Plan General de Ordenación Urbana (1990)', [
            ('Plano', '/files/plano.pdf?download=1'), ('Memoria', '/files/pgou.pdf'),
        ])
        rows = BenetusserAyuntamientoAdapter.parse_inventory(html)
        pgou = next(row for row in rows if row['tipo'] == 'PGOU')
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(pgou['documentos']), 2)
        self.assertIn('https://www.benetusser2030.es/files/plano.pdf?download=1',
                      [doc['url'] for doc in pgou['documentos']])
        self.assertTrue(all(doc['url_origen'] == SOURCE for doc in pgou['documentos']))

    def test_continuation_fails_instead_of_truncating(self):
        for continuation in ['<a rel="next" href="?page=2">2</a>',
                             '<div class="pagination"><a href="?page=2">2</a></div>',
                             '<button>Cargar más</button>']:
            with self.subTest(continuation=continuation), self.assertRaises(ValueError):
                BenetusserAyuntamientoAdapter.parse_inventory(catalogue() + continuation)

    def test_missing_records_documents_or_changed_markup_fail(self):
        for html in ['<h1>Iniciar sesión</h1>', catalogue().replace('inner-toggle-wrap', 'changed'),
                     catalogue().replace('PUAM Plan Urbano de Actuación Municipal 2022', 'Nuevo plan')]:
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                BenetusserAyuntamientoAdapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            BenetusserAyuntamientoAdapter.parse_inventory(catalogue().replace('/files/pgou.pdf', 'https://example.org/pgou.pdf'))

    def test_manifest_and_full_refresh_and_disabled_licences(self):
        manifest = load_manifest('benetusser')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46054')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        adapter = BenetusserAyuntamientoAdapter('benetusser')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            path.write_text('stale data\n')
            adapter._write(path, adapter.parse_inventory(catalogue()))
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 4)
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 4}) as refresh:
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state.json'), {'rows': 4})
                refresh.assert_called_once_with(path)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
