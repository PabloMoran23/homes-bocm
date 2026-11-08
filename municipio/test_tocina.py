import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tocina import (
    ADAPTACION, DOC_ROOT, PGOU, TocinaAyuntamientoAdapter, make_records, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def adaptation(*names, next_page=False):
    links = ''.join(f'<a href="{DOC_ROOT}{n}.pdf">{n}</a>' for n in names)
    page = f'<a href="{ADAPTACION}?pagegalleryfiles-2-1=2#galleryfiles-2-1">2</a>' if next_page else ''
    return f'<article class="documentacion">{links}{page}</article>'


class TocinaTests(unittest.TestCase):
    def test_group_documents_and_preserve_provenance(self):
        groups, pages = parse_inventory(adaptation('Memoria', 'PLANOS/PO-1',
            'CORRECCION-ERROR-MATERIAL-PGOU', 'INFORME_CORRECCION', next_page=True), ADAPTACION, 'adaptacion')
        self.assertEqual({k: len(v) for k, v in groups.items()}, {'adaptacion-loua': 2, 'correccion-adaptacion': 2})
        self.assertEqual(len(pages), 1)
        for row in make_records(groups):
            self.assertEqual(row['codigo_ine'], '41092')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon'):
                self.assertNotIn(field, row)
            self.assertTrue(all(d['inventory_url'] == ADAPTACION for d in row['documentos']))

    def test_pgou_maps_are_one_instrument(self):
        html = '''<div id="cuerpo"><p>Memoria <a href="http://multimedia.dipusevilla.es/tocina/pgou/m.pdf" title="Memoria">PDF</a></p>
        <a href="http://multimedia.dipusevilla.es/tocina/pgou/map.pdf" title="Plano">PDF</a>
        <a href="http://multimedia.dipusevilla.es/tocina/pgou/map.pdf" title="Plano">PDF</a></div>'''
        groups, _ = parse_inventory(html, PGOU, 'pgou')
        self.assertEqual(len(make_records(groups)), 1)
        self.assertEqual(len(groups['pgou']), 2)

    def test_fail_closed_on_empty_unknown_and_new_pagination(self):
        for html in ['<html>error</html>', '<div id="cuerpo">Formulario de licencia</div>',
                     '<div id="cuerpo"><a href="https://example.org/other.pdf">PDF</a></div>']:
            with self.assertRaises(ValueError):
                parse_inventory(html, PGOU, 'pgou')
        with self.assertRaises(ValueError):
            parse_inventory(adaptation('Memoria') + '<a href="?page=2">Siguiente</a>', ADAPTACION, 'adaptacion')

    def test_backfill_follows_second_page_and_update_is_snapshot(self):
        pgou = '<div id="cuerpo"><a href="http://multimedia.dipusevilla.es/tocina/pgou/m.pdf">Memoria</a></div>'
        page2 = ADAPTACION + '?pagegalleryfiles-2-1=2'
        bodies = {PGOU: pgou, ADAPTACION: adaptation('CORRECCION-ERROR-MATERIAL-PGOU', next_page=True),
                  page2: adaptation('Memoria')}
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            return type('Response', (), {'url': url, 'text': bodies[url], 'raise_for_status': lambda self: None})()
        with tempfile.TemporaryDirectory() as folder, patch('requests.Session.get', side_effect=get):
            path = Path(folder) / 'records.jsonl'
            adapter = TocinaAyuntamientoAdapter('tocina')
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['count'], 3)
            self.assertIn(page2, calls)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertTrue(any(d['inventory_url'] == page2 for r in rows for d in r['documentos']))
            before = path.read_text()
            adapter.update_proyectos(path, Path(folder) / 'state.json')
            self.assertEqual(before, path.read_text())

    def test_manifest(self):
        manifest = load_manifest('tocina')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('41092', 'Sevilla'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
