import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.puerto_serrano import (
    PREFIX, SOURCE, PuertoSerranoAyuntamientoAdapter, parse_detail, parse_inventory,
)


def inventory(items=None):
    if items is None:
        items = [('20474', 'ESTUDIO DE DETALLE PLAZA DIAMANTINO')]
    return '<p>Ayuntamiento de Puerto Serrano</p><div class="contenido_indicadores_seccion">' + ''.join(
        f'''<li onclick="window.open('https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?{PREFIX}entidadId=2001&amp;{PREFIX}indicadorId={key}', '_blank')">&gt; {title}</li>'''
        for key, title in items) + '</div>'


def detail(title='ESTUDIO DE DETALLE PLAZA DIAMANTINO', docs=('one.pdf', 'two.pdf')):
    return f'<p>Ayuntamiento de Puerto Serrano</p><div class="indicador_detalle"><h3>{title}</h3>' + ''.join(
        f'''<div class="indicador_detalle_distribuciones_item" onclick="location.href='https://gobiernoabierto.dipucadiz.es/uploads/indicadores/{doc}';">PDF</div>'''
        for doc in docs) + '<div class="indicador_detalle_datacion">Fecha de creación: 25/07/2025 12:31</div></div>'


class ParserTests(unittest.TestCase):
    def test_group_documents_and_do_not_infer_dates(self):
        row = parse_inventory(inventory())[0]
        result = parse_detail(detail(docs=('one.pdf', 'two.pdf', 'one.pdf')), row)
        self.assertEqual(len(result['documentos']), 2)
        self.assertEqual(result['codigo_ine'], '11029')
        self.assertEqual(result['fecha_creacion_ficha'], '25/07/2025 12:31')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, result)

    def test_filter_forms_tenders_news_and_deduplicate(self):
        html = inventory([('1', 'ESTUDIO DE DETALLE A'), ('1', 'ESTUDIO DE DETALLE A'),
                          ('2', 'SOLICITUD DE LICENCIA URBANÍSTICA'), ('3', 'Licitación obras'),
                          ('4', 'Noticias municipales')])
        self.assertEqual(len(parse_inventory(html)), 1)

    def test_fail_on_empty_wrong_entity_and_pagination(self):
        for html in ('<html>error</html>', inventory([]),
                     inventory().replace('entidadId=2001', 'entidadId=2002'),
                     inventory() + '<a href="?page=2">2</a>',
                     inventory() + '<a rel="next" href="?more=yes">Más</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_fail_on_mismatched_detail_or_missing_documents(self):
        row = parse_inventory(inventory())[0]
        for html in (detail(title='Other'), detail(docs=()),
                     detail().replace('https://gobiernoabierto.dipucadiz.es/uploads/', 'https://example.org/uploads/')):
            with self.assertRaises(ValueError):
                parse_detail(html, row)

    def test_documents_remain_with_their_instrument(self):
        rows = parse_inventory(inventory([('1', 'ESTUDIO DE DETALLE A'), ('2', 'PLAN PARCIAL B')]))
        a = parse_detail(detail(title=rows[0]['titulo'], docs=('a.pdf',)), rows[0])
        b = parse_detail(detail(title=rows[1]['titulo'], docs=('b.pdf',)), rows[1])
        self.assertNotEqual(a['documentos'], b['documentos'])

    def test_live_path_refresh_and_no_partial_overwrite(self):
        adapter = PuertoSerranoAyuntamientoAdapter('puerto-serrano')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail()]):
                self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state')['count'], 1)
            previous = output.read_text()
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail(docs=())]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), previous)


if __name__ == '__main__':
    unittest.main()
