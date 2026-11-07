"""Offline parser/contract regression tests; live evidence is collected separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tafalla import (
    INVENTORY, TafallaAyuntamientoAdapter, parse_inventory, parse_page,
)
from municipio.manifest import load_manifest, load_yaml

PERI = INVENTORY + 'peri-centro-historico/'
PMUS = INVENTORY + 'plan-de-movilidad-urbana-sostenible/'


def page(title, body):
    return f'<main><div class="contenido"><h2>{title}</h2>{body}</div><aside><a href="/unrelated.pdf">Other</a></aside></main>'


INDEX = page('Normativa urbanística', f'''
<a href="{PERI}">PERI Centro Histórico</a>
<a href="{PMUS}">Plan de movilidad urbana sostenible</a>
<a href="{INVENTORY}proyecto-sudeau-rio-cidacos/">Diagnóstico</a>
<a href="https://sedeelectronica.tafalla.es/">Solicitud de licencia</a>''')


class TafallaTests(unittest.TestCase):
    def test_inventory_scope_and_missing_collection(self):
        self.assertEqual(set(parse_inventory(INDEX)), {PERI, PMUS})
        with self.assertRaises(ValueError):
            parse_inventory(INDEX.replace(PMUS, INVENTORY + 'other/'))
        with self.assertRaises(ValueError):
            parse_inventory('<html>Access denied</html>')

    def test_no_silent_pagination(self):
        for link in ['<a href="?paged=2">2</a>', '<a rel="next" href="?p=2">Go</a>',
                     '<a class="page-numbers" href="/page/2/">2</a>']:
            with self.subTest(link=link), self.assertRaises(ValueError):
                parse_page(page('Plan', link), PERI)

    def test_group_documents_provenance_and_unknown_dates(self):
        child = PERI + 'planos/'
        pdf = 'https://www.tafalla.es/wp-content/uploads/2012/10/plan.pdf'
        pages = {INVENTORY: INDEX,
                 PERI: page('PERI Centro Histórico', f'<a href="{child}">Planos</a>'),
                 child: page('Planos', f'<a href="{pdf}">Plano</a><a href="{pdf}#p=2">Duplicate</a>'),
                 PMUS: page('Plan de movilidad urbana sostenible', '<a href="/wp-content/uploads/2020/09/Memoria-1.pdf">Memoria</a>')}
        with tempfile.TemporaryDirectory() as tmp, patch.object(TafallaAyuntamientoAdapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'projects.jsonl'
            adapter = TafallaAyuntamientoAdapter('tafalla')
            result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len(rows[0]['documentos']), 1)
            self.assertEqual(rows[0]['documentos'][0]['source_pages'], [child])
            self.assertEqual(rows[0]['documentos'][0]['url'], pdf)
            self.assertIn(child, result['source_urls'])
            for row in rows:
                self.assertEqual(row['codigo_ine'], '31227')
                for key in ['fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
                    self.assertIsNone(row[key])
            ids = [r['id'] for r in rows]
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(ids, [json.loads(l)['id'] for l in out.read_text().splitlines()])

    def test_missing_documents_preserves_previous_output(self):
        pages = {INVENTORY: INDEX, PERI: page('PERI Centro Histórico', '<p>Empty</p>')}
        with tempfile.TemporaryDirectory() as tmp, patch.object(TafallaAyuntamientoAdapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                TafallaAyuntamientoAdapter('tafalla').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tafalla')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('31227', 'Tafalla', 'Navarra'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp, patch.object(TafallaAyuntamientoAdapter, '_fetch') as fetch:
            out = Path(tmp) / 'licencias.jsonl'
            result = TafallaAyuntamientoAdapter('tafalla').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
