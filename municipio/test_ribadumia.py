import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ribadumia import (
    RibadumiaAyuntamientoAdapter, SOURCE, group_projects, parse_page,
)
from municipio.manifest import load_manifest


def entry(title, doc='a', date='14/6/24'):
    return (f'<div class="media-body"><div class="media-heading"><span class="h4">'
            f'{title}<small>{date}</small></span></div><p class="text-sm">Source description</p>'
            f'<a href="/cargararchivo.aspx?id={doc}" title="{doc}.pdf">Arquivo</a></div>')


def page(body, current=1, total=2, size=1):
    pages = (total + size - 1) // size
    options = ''.join(f'<option value="{n}" {"selected" if n == current else ""}>{n}</option>'
                      for n in range(1, pages + 1))
    return (f'<input type="hidden" name="__VIEWSTATE" value="state-{current}">'
            f'<select id="x_dlPagina" name="page" title="{total} Rexistros">{options}</select>'
            f'<select id="x_dlResultados" name="size"><option selected value="{size}"></option></select>' + body)


class ParserTests(unittest.TestCase):
    def test_group_documents_dates_exclusions(self):
        titles = ['MODIFICACACIÓN PUNTUAL NUMERO 5 - PLANOS',
                  'MODIFICACIÓN PUNTUAL NUMERO 5 - MEMORIA',
                  'PLAN DE ACCESIBILIDADE DO NÚCLEO URBANO DE BARRANTES (2025)',
                  'Solicitude de licenza', 'Contratos Menores', 'Ordenanza municipal']
        html = page(''.join(entry(t, str(i)) for i, t in enumerate(titles)), total=6, size=6)
        entries, meta, _ = parse_page(html)
        records = group_projects(entries + [entries[0]])
        self.assertEqual(meta, (1, 1, 6))
        self.assertEqual(len(records), 2)
        mp = next(r for r in records if r['tipo'] == 'modificacion_planeamiento')
        self.assertEqual(len(mp['documentos']), 2)
        self.assertEqual(mp['fecha_publicacion'], '2024-06-14')
        self.assertIsNone(mp['fecha_acuerdo'])
        self.assertIsNone(mp['fecha_aprob'])
        self.assertIsNone(mp['geometry'])
        self.assertEqual(mp['documentos'][0]['titulo'], '0.pdf')
        self.assertEqual(mp['publicaciones'][0]['descripcion'], 'Source description')
        records = group_projects([entries[0], {**entries[1], 'fecha_publicacion': '2024-07-01'}])
        self.assertIsNone(records[0]['fecha_publicacion'])

    def test_fail_closed_on_missing_rows_documents_and_markup(self):
        for html in ['<html>error</html>', page('', total=1)]:
            with self.assertRaises(ValueError):
                parse_page(html)
        entries, _, _ = parse_page(page(entry('MODIFICACACIÓN PUNTUAL NUMERO 5 - PLANOS'), total=1))
        entries[0]['documentos'] = []
        with self.assertRaises(ValueError):
            group_projects(entries)
        with self.assertRaises(ValueError):
            group_projects([])

    def test_all_pages_and_repeated_page_rejected(self):
        class Response:
            url = SOURCE
            def __init__(self, text): self.text = text
            def raise_for_status(self): pass
        first = Response(page(entry('MODIFICACACIÓN PUNTUAL NUMERO 5 - PLANOS')))
        second = Response(page(entry('MODIFICACACIÓN PUNTUAL NUMERO 5 - MEMORIA', 'b'), current=2))
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.ribadumia.requests.Session') as factory, patch('municipio.adapters.ribadumia.time.sleep'):
            session = factory.return_value.__enter__.return_value
            session.get.return_value = first
            session.post.return_value = second
            output = Path(d) / 'proyectos.jsonl'
            adapter = RibadumiaAyuntamientoAdapter('ribadumia')
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['pages'], 2)
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)
            self.assertEqual(session.post.call_args.kwargs['data']['__VIEWSTATE'], 'state-1')
            session.post.return_value = first
            with self.assertRaises(ValueError):
                adapter.update_proyectos(output, Path(d) / 'state.json')
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)
            self.assertEqual(adapter.backfill_licencias(Path(d) / 'lic.jsonl')['rows'], 0)

    def test_manifest(self):
        manifest = load_manifest('ribadumia')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
