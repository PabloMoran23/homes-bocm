import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.fisterra import (
    BASE, INDEX, FisterraAyuntamientoAdapter, content, inventory_links, parse_plan,
)
from municipio.manifest import load_manifest, load_yaml


def page(heading, body):
    return f'<div id="info"><section class="colcontido"><h2>{heading}</h2>{body}</section></div>'


class FisterraTests(unittest.TestCase):
    def test_explicit_dates_have_separate_meanings(self):
        row = parse_plan(page('Plan Xeral de Ordenación Municipal',
            '<p class="intro"><p>PXOM aprobado pola Orde da Xunta do 5/08/2019 '
            'e publicado no BOP de data 7/08/2020</p></p>'), 'pxom')
        self.assertEqual(row['fecha_aprob'], '2019-08-05')
        self.assertEqual(row['fecha_publicacion'], '2020-08-07')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])

    def test_initial_stage_is_not_final_or_dated_from_filename(self):
        row = parse_plan(page('PEPRICH', '<p class="intro">Nova Aprobación Inicial '
            'por existencia de modificacións sustanciais do Plan Especial.</p>'
            '<a href="202008.pdf">2020</a>'), 'peprich')
        self.assertIn('inicial', row['fase'])
        for key in ['fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_all_pdf_links_retained_and_duplicate_links_grouped(self):
        html = page('Catálogo', '<h3><a href="/media/a.pdf">Catálogo</a></h3>'
            '<a href="/media/a.pdf">Descargar</a><li><a href="/media/b.pdf">Quinteiro</a></li>'
            '<a href="../descargas_areas/gl/166">Catálogo</a>')
        cats, docs = inventory_links(html, BASE + '/portal_cidadan/peprich/gl')
        self.assertEqual(len(docs), 2)
        self.assertEqual(len(cats), 1)
        self.assertEqual(docs[BASE + '/media/b.pdf']['titulo'], 'Quinteiro')
        self.assertEqual(docs[BASE + '/media/a.pdf']['source_url'], BASE + '/portal_cidadan/peprich/gl')

    def test_reject_navigation_empty_content_and_pagination(self):
        for html in ['<a href="pxom/gl">Plan Xeral</a>',
                     page('PEPRICH', '<p>Text</p><a rel="next" href="?page=2">2</a>'),
                     page('PEPRICH', '<div class="pagination"><a href="?p=2">2</a></div>')]:
            with self.assertRaises(ValueError):
                content(html)
        with self.assertRaises(ValueError):
            parse_plan(page('PEPRICH', ''), 'peprich')

    def test_complete_snapshot_groups_category_documents(self):
        index = '<div id="columna"><ul class="menu">' + ''.join(
            f'<li><a href="/portal_cidadan/{key}/gl">Plan</a></li>' for key in ['pxom', 'peprich']) + '</ul></div>'
        sources = {INDEX: index}
        for key, title, number in [('pxom', 'Plan Xeral de Ordenación Municipal', 130), ('peprich', 'PEPRICH', 160)]:
            sources[BASE + f'/portal_cidadan/{key}/gl'] = page(title,
                f'<p class="intro">Instrumento de Fisterra</p><a href="/portal_cidadan/descargas_areas/gl/{number}">Docs</a>')
            sources[BASE + f'/portal_cidadan/descargas_areas/gl/{number}'] = page('Docs',
                f'<a href="/media/{key}1.pdf">Memoria</a><a href="/media/{key}2.pdf">Planos</a>')
        adapter = FisterraAyuntamientoAdapter('fisterra')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            path = Path(folder) / 'projects.jsonl'
            adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(len(r['documentos']) == 2 for r in rows))
            before = path.read_bytes()
            sources[BASE + '/portal_cidadan/descargas_areas/gl/160'] = page('Docs', '')
            with self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(folder) / 'state')
            self.assertEqual(path.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('fisterra')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '15037')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'licencias.jsonl'
            result = FisterraAyuntamientoAdapter('fisterra').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
