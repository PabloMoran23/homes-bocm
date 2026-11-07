import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from municipio.adapters.bullas import BullasAyuntamientoAdapter, SOURCE, parse_folder, parse_inventory


def folder(rows, count=None):
    return '<table role="grid" aria-rowcount="%s">%s</table>' % (
        len(rows) if count is None else count,
        ''.join(f'<tr data-id="{ident}"><td><strong>{name}</strong></td></tr>' for ident, name in rows))


class BullasTests(unittest.TestCase):
    def test_only_real_instrument_link(self):
        html = '<a href="form.pdf">Solicitud licencia</a><a href="https://bit.ly/example">APROBACIÓN PROVISIONAL PGMO</a>'
        row = parse_inventory(html, SOURCE)
        self.assertEqual(row['codigo_ine'], '30012')
        self.assertFalse(any(k in row for k in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon')))
        with self.assertRaises(ValueError):
            parse_inventory('<a href="form.pdf">Licencia obras</a>', SOURCE)

    def test_complete_folder_and_fail_closed(self):
        docs = parse_folder(folder([('abc', 'Normas.pdf'), ('def', 'Planos')]), 'root')
        self.assertEqual([d['tipo'] for d in docs], ['pdf', 'carpeta'])
        self.assertEqual(docs[0]['inventory_url'], 'root')
        for html in (folder([('abc', 'Normas.pdf')], 2), folder([]), '<h1>Login</h1>', folder([('abc', 'x.pdf')]) + '<a rel="next" href="page2">Next</a>'):
            with self.assertRaises(ValueError):
                parse_folder(html, 'root')

    def test_manifest_and_failed_live_preserves_output(self):
        from municipio.manifest import load_manifest, load_yaml
        from municipio.adapters.registry import load_portal_adapter
        manifest = load_manifest('bullas')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('30012', 'Murcia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), BullasAyuntamientoAdapter)
        adapter = BullasAyuntamientoAdapter('bullas')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=SimpleNamespace(url=SOURCE, text='<p>Unavailable</p>')):
            path = Path(tmp) / 'out.jsonl'
            path.write_text('previous output')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous output')

    def test_groups_nested_documents_and_update(self):
        root = 'https://drive.google.com/drive/folders/root'
        child = 'https://drive.google.com/drive/folders/child'
        responses = {
            SOURCE: SimpleNamespace(url=SOURCE, text=f'<a href="{root}">APROBACIÓN PROVISIONAL PGMO</a>'),
            root: SimpleNamespace(url=root, text=folder([('child', 'Planos'), ('norm', 'Normas.pdf')])),
            child: SimpleNamespace(url=child, text=folder([('map', 'Plano.pdf')])),
        }
        adapter = BullasAyuntamientoAdapter('bullas')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda url, name: responses[url]):
            path = Path(tmp) / 'out.jsonl'
            result = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(rows[0]['documentos']), 3)
            self.assertEqual(rows[0]['documentos'][-1]['inventory_url'], child)


if __name__ == '__main__':
    unittest.main()
