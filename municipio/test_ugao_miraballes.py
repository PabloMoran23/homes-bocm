import tempfile
import unittest
from pathlib import Path

from municipio.adapters.ugao_miraballes import (
    BASE, INVENTORY, PREFIX, UgaoMiraballesAyuntamientoAdapter, parse_page,
)


class UgaoTests(unittest.TestCase):
    def test_group_sections_deduplicate_and_preserve_provenance(self):
        root = BASE + PREFIX + '.aspx'
        child = BASE + PREFIX + '-memorias.aspx'
        second = child + '?page=2'
        pdf = '/es-ES/Servicios/Urbanismo/apro_def_texto_redifundido_memorias/01.PDF'
        pages = {
            INVENTORY: f'<a href="{root}">Plan General de Ordenación Urbana - Aprobación definitiva</a><a href="/formulario.aspx">Licencia</a>',
            root: f'<a href="{child}">Memorias</a><a href="{pdf}">Memoria</a>',
            child: f'<a href="{second}">&gt;</a><a href="{root}">Volver</a><a href="{pdf}">Memoria</a><a href="https://other.example/a.pdf">Otro</a>',
        }
        pages[second] = '<a href="/es-ES/Servicios/Urbanismo/anexo.pdf">Anexo</a>'
        rows = UgaoMiraballesAyuntamientoAdapter('ugao-miraballes').extract(pages.__getitem__)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(set(next(d for d in row['documentos'] if d['url'].endswith('01.PDF'))['indices']), {root, child})
        self.assertEqual(row['codigo_ine'], '48065')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])

    def test_fail_closed_on_pagination_or_missing_source(self):
        for html in ['<a rel="next" href="?page=2">2</a>', '<a href="?Paged=TRUE">2</a>']:
            with self.assertRaises(ValueError):
                parse_page(html, INVENTORY)
        adapter = UgaoMiraballesAyuntamientoAdapter('ugao-miraballes')
        with self.assertRaises(ValueError):
            adapter.extract(lambda url: '<a href="/licencia.pdf">Solicitud</a>')
        root = BASE + PREFIX + '.aspx'
        with self.assertRaises(ValueError):
            adapter.extract(lambda url: f'<a href="{root}">PGOU</a>')

    def test_failed_refresh_preserves_output_and_licences_disabled(self):
        adapter = UgaoMiraballesAyuntamientoAdapter('ugao-miraballes')
        adapter._fetch = lambda url: '<html>error</html>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.jsonl'
            path.write_text('previous\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous\n')
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
