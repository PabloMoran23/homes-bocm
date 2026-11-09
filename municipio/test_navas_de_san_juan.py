import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.navas_de_san_juan import (
    NavasDeSanJuanAyuntamientoAdapter, PREPARATION, REGISTER,
    explicit_date, parse_preparation, parse_register,
)


def page(body):
    return '<div class="et_pb_post_content">' + body + '</div>'


def register_row(number, title, approval='1995', publication='BOP-2019-679'):
    return '<tr>' + ''.join('<td>' + v + '</td>' for v in
                           [str(number), title, approval, publication, 'Ayuntamiento', '–']) + '</tr>'


def register(*rows):
    return page('<table><tr><td>APROBACIÓN DEFINITIVA</td></tr>' + ''.join(rows) + '</table>')


PREP = page('''<p><strong>1. EXPEDIENTE</strong></p>
<p><a href="/avance.pdf">Acuerdo plenario 20/09/2022</a></p>
<p><strong>4. – ESTUDIO DE ORDENACIÓN (CALLE CRUZ, 15)</strong></p>
<p><a href="/cruz.pdf">Documento de Aprobación Inicial</a></p>
<p><a href="/cruz-firmado.pdf">Estudio de Ordenación Firmado</a></p>
<p><strong>5. – APROBACIÓN INICIAL DEL PLAN BÁSICO (PBOM)</strong></p>
<p><a href="/pbom.pdf">Edicto de Aprobación Inicial en el BOP</a></p>''')


class ParserTests(unittest.TestCase):
    def test_explicit_dates_not_identifiers_or_years(self):
        self.assertIsNone(explicit_date('1995'))
        self.assertIsNone(explicit_date('BOP-2019-679'))
        self.assertEqual(explicit_date('07 de Marzo de 2019'), '2019-03-07')
        self.assertEqual(explicit_date('BOP 22 DE 28 ENERO 2010'), '2010-01-28')
        self.assertEqual(explicit_date('BOJA 62 de 01-04-2014'), '2014-04-01')
        self.assertIsNone(explicit_date('BOP 17 DICIEMBRE 2015 Corrección BOP 21-04-2016'))

    def test_register_excludes_ordinances_groups_documents(self):
        rows = parse_register(register(
            register_row(8, 'Modificación de NN.SS. (Fondos) <a href="/a.pdf">Original</a> <a href="/b.pdf">Corrección</a>',
                         '04 ABRIL 2016', 'BOP 17 DICIEMBRE 2015 Corrección BOP 21-04-2016'),
            register_row(10, 'Modificación de Ordenanza: Tasa y Base Imponible del ICIO'),
            register_row(3, 'Estudio de Detalle: Solar Nº 27 en Calle Carlos I')))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_aprob'], '2016-04-04')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIn('Corrección', rows[0]['publicacion_texto'])
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertEqual(rows[1]['aprobacion_texto'], '1995')

    def test_preparation_groups_pbom_across_sections(self):
        rows = {r['id'].rsplit('plan-', 1)[1]: r for r in parse_preparation(PREP)}
        self.assertEqual(set(rows), {'pbom', 'cruz-15'})
        self.assertEqual(len(rows['pbom']['documentos']), 2)
        self.assertEqual(len(rows['cruz-15']['documentos']), 2)
        self.assertEqual(rows['pbom']['fase'], 'aprobación inicial')
        self.assertIsNone(rows['pbom']['fecha_aprob'])
        self.assertIsNone(rows['pbom']['fecha_publicacion'])
        self.assertIsNone(rows['pbom']['geometry'])

    def test_changed_sources_fail_instead_of_partial_success(self):
        for html in ['<html>Request blocked</html>', PREP + '<a rel="next" href="/page/2">2</a>',
                     PREP.replace('5. – APROBACIÓN', '6. – APROBACIÓN'),
                     PREP.replace('4. – ESTUDIO', '9. – ESTUDIO')]:
            with self.assertRaises(ValueError):
                parse_preparation(html)
        with self.assertRaises(ValueError):
            parse_register(register(register_row(1, 'Unknown plan')))
        with self.assertRaises(ValueError):
            parse_register(register(register_row(1, 'Estudio de Detalle'), register_row(1, 'Estudio de Detalle')))

    def test_adapter_follows_detail_and_refreshes_complete_snapshot(self):
        inventory = register(register_row(1, 'Normas Subsidiarias <a href="/instrumento/">Detalle</a>'))
        sources = {REGISTER: inventory, PREPARATION: PREP,
                   'https://navasdesanjuan.es/instrumento/': page('<a href="/normas.pdf">Normas</a>')}
        adapter = NavasDeSanJuanAyuntamientoAdapter('navas-de-san-juan')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[0]['documentos'][1]['source_url'], 'https://navasdesanjuan.es/instrumento/')
            before = output.read_bytes()
            adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
