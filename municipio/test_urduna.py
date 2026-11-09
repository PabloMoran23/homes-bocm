"""Parser and completeness checks; run with python -m unittest municipio.test_urduna."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.urduna import SOURCE, UrdunaAyuntamientoAdapter, group_documents, parse_page
from municipio.manifest import load_manifest


def section(title, body):
    return f'<div><div><h3 class="ms-WPTitle">{title}</h3></div><div class="ms-WPBody">{body}</div></div>'


def page(start, end, total, names, links=()):
    files = ''.join(f'<a href="/es-ES/Servicios/Urbanismo/PGOUautocad/{n}">{n}</a>' for n in names)
    pagination = '<ul class="pagination">' + ''.join(f'<li><a href="{SOURCE}?page={n}">{n}</a></li>' for n in links) + '</ul>'
    return section('PGOU 2004', f'Resultados {start} - {end} de {total}' + files + pagination)


class UrdunaTests(unittest.TestCase):
    def test_group_instruments_and_preserve_provenance(self):
        html = page(1, 3, 3, ['001_MEMORIA.pdf', 'fase-3-avance-cas.pdf',
                                     '20250915-10_aprobarcion-criterios.pdf'])
        html += section('Plan Especial de Rehabilitación del Casco Histórico',
                        '<a href="/per-parte1.pdf">Parte 1</a><a href="/per-parte2.pdf">Parte 2</a>')
        html += section('Modificaciones de planeamiento pormenorizadas',
                        '<a href="/mod.pdf">1ª Modificación Puntual del Plan Especial La Estación (PDF 4MB)</a>')
        html += section('Estudios', '<a href="/estudio.pdf">Estudio tráfico</a>')
        docs, _, _ = parse_page(html)
        rows = group_documents(docs + docs)
        self.assertEqual(len(rows), 4)
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [1, 1, 2, 2])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in group_documents(docs)])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '48074')
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['geometry'])
        self.assertFalse(any('estudio.pdf' in d['url'] for r in rows for d in r['documentos']))

    def test_full_pagination_live_methods(self):
        pages = {SOURCE: page(1, 1, 2, ['001_MEMORIA.pdf'], [1, 2]),
                 SOURCE + '?page=2': page(2, 2, 2, ['fase-3-avance-cas.pdf'], [1, 2])}
        with tempfile.TemporaryDirectory() as tmp, patch.object(UrdunaAyuntamientoAdapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'proyectos.jsonl'
            result = UrdunaAyuntamientoAdapter().update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['pages'], 2)
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)

    def test_incomplete_or_repeated_pagination_preserves_output(self):
        first = page(1, 1, 2, ['001_MEMORIA.pdf'], [2])
        for second in [page(1, 1, 2, ['001_MEMORIA.pdf']),
                       page(2, 2, 2, ['001_MEMORIA.pdf']),
                       page(2, 2, 3, ['fase-3-avance-cas.pdf'])]:
            with tempfile.TemporaryDirectory() as tmp, patch.object(UrdunaAyuntamientoAdapter, '_fetch', side_effect=[first, second]):
                out = Path(tmp) / 'projects.jsonl'
                out.write_text('previous snapshot')
                with self.assertRaises(ValueError):
                    UrdunaAyuntamientoAdapter().backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'previous snapshot')
        with tempfile.TemporaryDirectory() as tmp, patch.object(UrdunaAyuntamientoAdapter, '_fetch', return_value=page(1, 1, 2, ['001_MEMORIA.pdf'])):
            with self.assertRaises(ValueError):
                UrdunaAyuntamientoAdapter().backfill_proyectos(Path(tmp) / 'projects.jsonl')

    def test_fail_closed_on_changed_inventory(self):
        for html in ['<html>Login</html>', page(1, 2, 2, ['001_MEMORIA.pdf'])]:
            with self.assertRaises(ValueError):
                parse_page(html)
        docs, _, _ = parse_page(page(1, 1, 1, ['unknown-plan.pdf']))
        with self.assertRaises(ValueError):
            group_documents(docs)
        with self.assertRaises(ValueError):
            parse_page(page(1, 1, 1, ['001_MEMORIA.pdf'], [2]).replace(SOURCE + '?page=2', 'https://example.com/?page=2'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('urduna')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Bizkaia')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(UrdunaAyuntamientoAdapter().backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
