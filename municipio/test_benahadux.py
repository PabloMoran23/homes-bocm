import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.benahadux import (
    SOURCE, BenahaduxAyuntamientoAdapter, parse_inventory, parse_project,
)


def inventory(paths, pager=''):
    return '<div class="view-obras-en-curso">' + ''.join(
        f'<article class="node--type-obras-y-proyectos"><h3><a href="{p}">Obra</a></h3></article>'
        for p in paths) + pager + '</div>'


def detail(title='Pabellón', doc='pabellon.pdf'):
    return f'''<h1>Unrelated page title</h1>
    <article class="node--type-obras-y-proyectos node--view-mode-full">
    <h1 class="project-detail__title">{title}</h1>
    <div class="field--name-field-estados"><div class="field__item">Planificado</div></div>
    <div class="field--name-field-extracto">Proyecto básico aprobado, sin fecha de acuerdo.</div>
    <div class="field--name-field-text-long-format">Construcción en parcelas ED y ES de UA-14.</div>
    <div class="field--name-field-fecha-de-inicio"><time datetime="2026-08-01T12:00:00Z"></time></div>
    <a href="/files/{doc}">Memoria</a><a href="/files/{doc}">Duplicado</a>
    <a href="/files/plano-{doc}">Plano</a></article>
    <footer><a href="/files/otra.pdf">Documento ajeno</a></footer>'''


class BenahaduxTests(unittest.TestCase):
    def test_document_grouping_and_date_meaning(self):
        row = parse_project(detail(), SOURCE + 'obras/pabellon', [SOURCE])
        self.assertEqual(row['titulo'], 'Pabellón')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_inicio'], '2026-08-01')
        for key in ('fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob'):
            self.assertIsNone(row[key])
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])
        other = parse_project(detail('Residencia', 'residencia.pdf'), SOURCE + 'obras/residencia', [SOURCE])
        self.assertNotEqual(row['id'], other['id'])
        self.assertTrue(all('residencia' in d['url'] for d in other['documentos']))

    def test_rejects_generic_news_forms_and_missing_inventory(self):
        for html in ('<a href="/licencia.pdf">Licencia</a>', '<h1>Noticias</h1>', inventory([])):
            with self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)
            with self.assertRaises(ValueError):
                parse_project(html, SOURCE + 'obras/x', [SOURCE])

    def test_pagination_and_deduplication(self):
        pages = {
            SOURCE: inventory(['/obras/a'], '<nav class="pager"><a href="?page=1">2</a></nav>'),
            SOURCE + '?page=1': inventory(['/obras/a', '/obras/b'], '<nav class="pager"><a href="/">1</a></nav>'),
            SOURCE + 'obras/a': detail('Pabellón', 'a.pdf'),
            SOURCE + 'obras/b': detail('Residencia', 'b.pdf'),
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(BenahaduxAyuntamientoAdapter, '_fetch', side_effect=pages.__getitem__):
            path = Path(tmp) / 'rows.jsonl'
            result = BenahaduxAyuntamientoAdapter().update_proyectos(path, Path(tmp) / 'state')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(result['count'], 2)
        self.assertEqual(len(rows[0]['inventory_urls']), 2)

    def test_dynamic_pagination_and_external_links_fail(self):
        for html in (inventory(['/obras/a'], '<a class="use-ajax" href="?page=1">Más</a>'),
                     inventory(['https://example.org/obras/a'])):
            with self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = BenahaduxAyuntamientoAdapter().backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
