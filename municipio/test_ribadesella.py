import tempfile
import unittest
from pathlib import Path

from municipio.adapters.ribadesella import SOURCE, RibadesellaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def section(title='CIUDADES SALUDABLES (PRTR)', code='C18.I02.P02.SI01', body=None):
    if body is None:
        body = ('<p>Nuevos elementos de juego en Bones y Collera.</p>'
                '<p><a href="/documents/proyecto.pdf">Memoria</a></p>'
                '<p><a href="/documents/anexo.pdf">Anexo</a></p>')
    return f'<p><b>{title}</b></p><p>{code}</p>{body}'


def inventory(content):
    return ('<div class="journal-content-article"><div class="titulo">'
            '<h2>Proyectos Financiados en el Ayuntamiento de Ribadesella</h2></div>'
            f'<div class="detalle">{content}</div></div>'
            '<div class="journal-content-article"><div class="detalle">Copyright</div></div>')


class RibadesellaTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_dates(self):
        rows = parse_inventory(inventory(section() + section()))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['referencia_prtr'], 'C18.I02.P02.SI01')
        self.assertEqual(row['codigo_ine'], '33056')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], 'https://www.ayto-ribadesella.es/documents/proyecto.pdf')
        self.assertEqual(row['documentos'][0]['procedencia'], SOURCE)
        self.assertIn('Bones y Collera', row['descripcion'])
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon'):
            self.assertNotIn(key, row)

    def test_scope_and_code_whitespace(self):
        html = inventory(section('MEJORA DE LA EFICIENCIA Y REDUCCIÓN DE PÉRDIDAS EN EL USO DEL AGUA',
                                 'C05. I01.P02.S06') +
                         section('COMPRA DE LIBROS EN PAPEL', 'C24.I02.P04.S03') +
                         section('AULA MENTOR', 'C20.I01.P03.PROV.S13.11') +
                         section('PLAN DE SOSTENIBILIDAD TURÍSTICA EN DESTINO', 'C14.I01.P07.S10'))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['referencia_prtr'], 'C05.I01.P02.S06')

    def test_reject_empty_changed_or_incomplete_inventory(self):
        for html in ('<html>Forbidden</html>', inventory(''), inventory(section(code='2023')),
                     inventory(section(body='')), inventory(section('PROYECTO NUEVO')),
                     inventory(section(body='<p> </p>'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_never_silently_ignored(self):
        for link in ('<a href="?page=2">2</a>', '<a href="/more" rel="next">2</a>',
                     '<a href="/more">Siguiente</a>'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                parse_inventory(inventory(section()) + link)

    def test_conflicting_duplicate(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory(section() + section(body='<p>Otro proyecto</p>')))

    def test_disabled_licences_and_manifest(self):
        m = load_manifest('ribadesella')
        self.assertEqual(m.provincia, 'Asturias')
        self.assertFalse(m.licencias.enabled)
        adapter = RibadesellaAyuntamientoAdapter('ribadesella')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
