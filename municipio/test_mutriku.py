"""Offline parser and snapshot contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.mutriku import MutrikuAyuntamientoAdapter as Adapter, SOURCE, content
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(body, nav=''):
    return '<div id="parent-fieldname-text">' + body + '</div>' + nav


def link(title, path, uid=''):
    return f'<a data-linktype="internal" data-val="{uid}" href="{path}">{title}</a>'


ROOT = page(link('Normas Subsidiarias de Mutriku (BOG 23-07-2007)', SOURCE + '/normas.pdf') +
            link('Memoria', SOURCE + '/memoria.pdf') +
            link('Sistemas Generales de Mutriku', SOURCE + '/sistemas.pdf') +
            link('Ordenanza de ruidos', SOURCE + '/ruidos.pdf'),
            ''.join(link(t, SOURCE + '/' + p) for t, p in [
                ('PLANOS GENERALES', 'planos'), ('CATALOGO', 'catalogo'),
                ('FICHAS URBANISTICAS', 'fichas'), ('MODIFICACIÓN PUNTUAL', 'modificaciones')]))
MODS = SOURCE + '/modificaciones'
DETAIL = MODS + '/ar9'
DETAIL_HTML = page('<p><strong>Egoera:</strong> Formulazio akordioaren argitalpena eta parte hartze programa</p>' +
                   link('Argitalpena: GAO', SOURCE + '/gazette.pdf'))


class ParserTests(unittest.TestCase):
    def test_grouped_snapshot_dates_provenance_and_extensionless_docs(self):
        inventory = page(link('1.- Modificación puntual AR-9 Motric y SR-1', DETAIL, 'stable-uid') * 2)
        pages = {SOURCE: ROOT, SOURCE + '/planos': page(link('Plano', SOURCE + '/shared.pdf')),
                 SOURCE + '/catalogo': page(link('Catálogo', SOURCE + '/catalogo.pdf')),
                 SOURCE + '/fichas': page(link('Plano duplicado', SOURCE + '/shared.pdf') +
                                          link('SI-1 - MIJOA', SOURCE + '/si1-mijoa-ii')),
                 MODS: inventory, DETAIL: DETAIL_HTML}
        adapter = Adapter('mutriku')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len(rows[0]['documentos']), 6)
            self.assertEqual(rows[0]['fecha_publicacion'], '2007-07-23')
            self.assertIn('BOG', rows[0]['fecha_publicacion_fuente']['ambito'])
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertIsNone(rows[0]['fecha'])
            self.assertIsNone(rows[1]['fecha_acuerdo'])
            self.assertIsNone(rows[1]['fecha_publicacion'])
            self.assertIn('Formulazio', rows[1]['fase_fuente'])
            self.assertFalse(rows[1]['publication_ready'])
            self.assertEqual(len(rows[1]['documentos']), 1)
            self.assertFalse(any('ruidos' in d['url'] for d in rows[0]['documentos']))
            self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state')['rows'], 2)

    def test_reject_changed_or_paginated_inventory(self):
        for markup in [page('Nothing'), ROOT.replace('CATALOGO', 'OTRO')]:
            with self.assertRaises(ValueError):
                Adapter.parse_root(markup)
        for pagination in ['<a href="?b_start:int=20">2</a>', '<a href="two" rel="next">More</a>',
                           '<a href="two">Siguiente</a>', '<a href="two">Hurrengoa</a>']:
            with self.assertRaises(ValueError):
                content(page('docs', pagination))
        with self.assertRaises(ValueError):
            Adapter.parse_amendments(page(link('Noticia ajena', DETAIL)), MODS)
        with self.assertRaises(ValueError):
            Adapter.parse_amendment(page('no attachments'), DETAIL, 'uid', 'plan')
        with self.assertRaises(ValueError):
            Adapter.parse_amendments(page(link('1.- Modificación puntual AR-9', 'https://example.org/plan')), MODS)

    def test_stable_instrument_id_and_disabled_licenses(self):
        first = Adapter.parse_amendment(DETAIL_HTML, DETAIL, 'uid', 'Original title')
        second = Adapter.parse_amendment(DETAIL_HTML, DETAIL, 'uid', 'Edited title')
        self.assertEqual(first['id'], second['id'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = Adapter('mutriku').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_failed_fetch_preserves_previous_snapshot(self):
        adapter = Adapter('mutriku')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=[ROOT, RuntimeError('offline')]):
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            with self.assertRaises(RuntimeError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')

    def test_manifest_and_registry_contract(self):
        manifest = load_manifest('mutriku')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '20056')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
