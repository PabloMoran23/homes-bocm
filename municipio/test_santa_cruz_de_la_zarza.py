import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_cruz_de_la_zarza import (
    SOURCE, SantaCruzDeLaZarzaAyuntamientoAdapter, inventory, parse_projects,
)
from municipio.manifest import load_manifest


def article(rows, narrative=''):
    return '<h1>Plan de ordenación municipal</h1><div itemprop="articleBody"><p>' + narrative + '</p><table>' + ''.join(
        '<tr><td>' + label + '</td><td><a href="/images/' + name + '.pdf">Ver Fichero</a></td></tr>' for label, name in rows
    ) + '</table></div>'


class SantaCruzTests(unittest.TestCase):
    def setUp(self):
        self.html = article([
            ('Plan de Ordenación Municipal - Índice', 'index'),
            ('Plan de Ordenación Municipal - Normas', 'norms'),
            ('Anuncio modificación puntual nº2', 'mp2'),
            ('Resolución modificación puntual nº2', 'wrong-label'),
            ('Memoria modificación puntual nº2', 'peri'),
            ('Planos modificación puntual nº2', 'peri-plans'),
        ], 'El Plan de Ordenación Municipal de Santa Cruz de la Zarza se aprobó definitivamente el 27 de Marzo de 2002.')
        self.texts = {
            'mp2': 'Número 118 Miércoles 25 de Mayo Año 2011\nSanta Cruz de la Zarza\nmodificación puntual número 2 aprobada definitivamente en sesión de fecha 31 de marzo de 2011.',
            'wrong-label': '28 de febrero de 2012\nResolución de 16/02/2012\nModificación Puntual Nº 3 del POM de Santa Cruz de la Zarza\nNo Sometimiento a Evaluación Ambiental',
            'peri': 'PERI-3 del Plan de Ordenación Municipal de Santa Cruz de la Zarza. ABRIL 2014',
            'peri-plans': 'PERI-3 del Plan de Ordenación Municipal de Santa Cruz de la Zarza. Planos',
        }
        self.texts = {SOURCE.split('/areas-')[0] + '/images/' + k + '.pdf': v for k, v in self.texts.items()}

    def test_content_corrects_wrong_labels_and_groups_all_documents(self):
        rows = parse_projects(self.html, self.texts)
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(len(r['documentos']) for r in rows), 6)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1, 1, 2])
        self.assertEqual(rows[2]['documentos'][0]['titulo_fuente'], 'Resolución modificación puntual nº2')
        self.assertIn('nº 3', rows[2]['titulo'])
        self.assertTrue(all(r['lat'] is None and r['geometry'] is None for r in rows))

    def test_dates_keep_publication_approval_and_environmental_act_separate(self):
        pom, mp2, mp3, peri = parse_projects(self.html, self.texts)
        self.assertEqual(pom['fecha_aprob'], '2002-03-27')
        self.assertIsNone(pom['fecha_publicacion'])
        self.assertEqual(mp2['fecha_publicacion'], '2011-05-25')
        self.assertEqual(mp2['fecha_aprob'], '2011-03-31')
        self.assertEqual(mp3['fecha_publicacion'], '2012-02-28')
        self.assertEqual(mp3['fecha_resolucion'], '2012-02-16')
        self.assertIsNone(mp3['fecha_aprob'])
        self.assertIsNone(peri['fase'])
        self.assertIsNone(peri['fecha_aprob'])

    def test_missing_or_unrecognized_pdf_fails(self):
        for texts in ({}, {k: 'Unknown instrument Santa Cruz de la Zarza' for k in self.texts}):
            with self.assertRaises(ValueError):
                parse_projects(self.html, texts)

    def test_empty_page_pagination_external_and_bad_rows_fail(self):
        for html in ('<html>Login</html>', article([]), self.html + '<a rel="next" href="?page=2">Next</a>',
                     self.html.replace('/images/index.pdf', 'https://other.example/index.pdf'),
                     self.html.replace('<a href="/images/index.pdf">Ver Fichero</a>', 'Unavailable')):
            with self.assertRaises(ValueError):
                inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('santa-cruz-de-la-zarza')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)
        adapter = SantaCruzDeLaZarzaAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')

    def test_live_path_does_not_overwrite_output_on_download_failure(self):
        adapter = SantaCruzDeLaZarzaAyuntamientoAdapter('santa-cruz-de-la-zarza')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_get', side_effect=[self.html.encode(), RuntimeError('HTTP failure')]):
                with self.assertRaises(RuntimeError):
                    adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(path.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
