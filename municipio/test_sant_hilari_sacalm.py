"""Offline semantic regression tests; fixtures model reviewed municipal markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_hilari_sacalm import (
    BASE, SOURCE, SantHilariSacalmAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest


def card(title, content, href):
    return f'<div class="item-medium"><div class="item-medium__description"><h2>{title}</h2><p>{content}</p></div><div class="button-more-wrapper"><a href="{href}">Més info</a></div></div>'


INVENTORY = '<div class="intro-category"><h1>Urbanisme</h1></div>' + ''.join([
    card('Pla General Municipal d’Ordenació Urbana',
         'Sant Hilari Sacalm. Va ser arpovat definitivament el 1994.', '/normativa.pdf'),
    card('Plànol d’ordenació urbana', 'Plànol general', '/mapa.pdf'),
    card('Avanç de planejament', 'Treballs previs al POUM', '/avanc/'),
    card('Programa de participació ciutadana', 'POUM', '/participacio/'),
    card('Llicència d’obres majors', 'Empleneu la sol·licitud', '/formulari.pdf'),
    card('Què és el POUM?', 'Explicació genèrica', '/explicacio/'),
])


def detail(title, filenames):
    return '<div class="intro-category"><h1>' + title + '</h1><p>POUM</p></div><div class="dowload-files">' + ''.join(
        f'<a href="/{f}.pdf">{f}</a>' for f in filenames) + '</div>'


ADVANCE = detail('Avanç de planejament', ['memoria', 'ambiental', 'planol', 'memoria'])
PARTICIPATION = detail('Programa de participació ciutadana', ['participacio'])


class PlanningTests(unittest.TestCase):
    def test_identity_grouping_and_semantics(self):
        pgm, urls = Adapter.parse_inventory(INVENTORY)
        self.assertEqual(urls, [BASE + '/avanc/', BASE + '/participacio/'])
        self.assertEqual(len(pgm['documentos']), 2)
        self.assertEqual(pgm['ano_aprobacion'], 1994)
        self.assertEqual(pgm['codigo_ine'], '17164')
        self.assertNotIn('formulari', json.dumps(pgm))
        poum = Adapter.parse_poum(list(zip(urls, [ADVANCE, PARTICIPATION])))
        self.assertEqual(len(poum['documentos']), 4)
        self.assertEqual(poum['fase'], 'avance de planeamiento')
        for row in (pgm, poum):
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(doc['source_url'] for doc in row['documentos']))

    def test_fail_on_missing_inventory_or_documents(self):
        for html in ('<h1>Urbanisme</h1>', INVENTORY.replace('Plànol d’ordenació urbana', 'Changed')):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            Adapter.parse_poum([(BASE + '/avanc/', detail('Avanç de planejament', [])),
                                (BASE + '/participacio/', PARTICIPATION)])
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(INVENTORY.replace('/normativa.pdf', 'https://example.org/foreign.pdf'))

    def test_fail_on_pagination(self):
        for extra in ('<a rel="next" href="/page/2">2</a>',
                      '<div class="pagination"><a href="/page/2">2</a></div>',
                      '<a href="/page/2">Següent</a>'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(INVENTORY + extra)
            with self.assertRaises(ValueError):
                Adapter.parse_poum([(BASE + '/avanc/', ADVANCE + extra),
                                    (BASE + '/participacio/', PARTICIPATION)])

    def test_live_workflow_snapshot_and_disabled_licences(self):
        adapter = Adapter('sant-hilari-sacalm')
        content = {SOURCE: INVENTORY, BASE + '/avanc/': ADVANCE,
                   BASE + '/participacio/': PARTICIPATION}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=content.__getitem__):
            out = Path(tmp) / 'projects.jsonl'
            adapter.backfill_proyectos(out)
            first = out.read_text()
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), first)
            self.assertEqual(len(first.splitlines()), 2)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'lic.jsonl')['status'], 'disabled')
            out.write_text('previous snapshot')
            content[BASE + '/avanc/'] = '<h1>Error</h1>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest(self):
        manifest = load_manifest('sant-hilari-sacalm')
        self.assertEqual(manifest.nombre, 'Sant Hilari Sacalm')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
