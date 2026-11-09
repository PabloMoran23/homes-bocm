"""Offline parser contracts; synthetic fixtures never enter the live output."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.velez_rubio import (
    SOURCE, VelezRubioAyuntamientoAdapter, group_notices, inventory,
    parse_notice, selected,
)

NOTICE = ('https://www.velezrubio.es/Servicios/cmsdipro/index.nsf/'
          'tablon.xsp?p=VelezR&documentId=' + 'A' * 32)


def fixture(title, date='03/02/2023', entity='Ayuntamiento de Vélez Rubio'):
    return f'''<div id="doc-dipalme-titulo"><h1>{title}</h1></div>
    <div id="doc-lectura-cultura"><div class="left"><h2>{entity}</h2></div>
    <div class="right">Publicado: <strong>{date}</strong></div>
    <table id="attachments"><tr><td><a href="/Servicios/Tablon/anexos.nsf/TEST/$file/proyecto.pdf">Proyecto</a></td>
    <td><a href="/Servicios/Tablon/anexos.nsf/TEST/$file/proyecto.pdf">descargar</a></td></tr></table></div>'''


class ParserTests(unittest.TestCase):
    def test_notice_provenance_and_date_semantics(self):
        n = parse_notice(fixture('Aprobación de Estudio de Detalle finca de prueba'), NOTICE)
        r, = group_notices([n])
        self.assertEqual(r['fecha_publicacion'], '2023-02-03')
        self.assertIsNone(r['fecha_acuerdo'])
        self.assertIsNone(r['fecha_aprob'])
        self.assertEqual(len(r['documentos']), 1)
        self.assertEqual(r['documentos'][0]['source_url'], NOTICE)
        self.assertNotIn('lat', r)
        self.assertFalse(r['publication_ready'])

    def test_group_two_stages_without_losing_documents_or_dates(self):
        titles = [
            'PROYECTO DE ACTUACIÓN “AMPLIACIÓN DE EXPLOTACIÓN PORCINA (616 cabezasnuevas), POLÍGONO 50 PARCELAS 174 y 180..PROMOTOR: PERSONA DE PRUEBA.',
            'PROYECTO DE ACTUACIÓN “AMPLIACIÓN DE EXPLOTACIÓN PORCINA (616 cabezas nuevas), POLÍGONO 50 PARCELAS 174 y 180. PROMOTOR: PERSONA DE PRUEBA.',
        ]
        n1 = parse_notice(fixture(titles[0]), NOTICE)
        n2 = parse_notice(fixture(titles[1], '09/05/2023'), NOTICE.replace('A' * 32, 'B' * 32))
        r, = group_notices([n1, n2])
        self.assertEqual(len(r['publicaciones']), 2)
        self.assertEqual(len(r['documentos']), 2)
        self.assertEqual(r['publicaciones'][1]['fecha_publicacion'], '2023-05-09')
        self.assertEqual(r['id'], group_notices([n2, n1])[0]['id'])
        n3 = parse_notice(fixture(titles[1].replace('174 y 180', '175 y 180')), NOTICE.replace('A' * 32, 'C' * 32))
        self.assertEqual(len(group_notices([n1, n2, n3])), 2)

    def test_exclude_forms_ordinances_news_and_procurement(self):
        for title in ['LICENCIA DE OBRA MENOR', 'ORDENANZA REGULADORA OBRAS',
                      'ADHESIÓN AL PACTO ANDALUZ DE ACCESIBILIDAD',
                      'Anuncio de licitación de obras', 'Noticias del municipio']:
            self.assertFalse(selected(title))
        with self.assertRaises(ValueError):
            parse_notice(fixture('LICENCIA DE OBRA MENOR'), NOTICE)

    def test_reject_other_municipalities_and_missing_documents(self):
        title = 'PROYECTO DE ACTUACIÓN de prueba'
        for html, url in [(fixture(title, entity='Ayuntamiento de Pulpí'), NOTICE),
                          (fixture(title), NOTICE.replace('p=VelezR', 'p=Pulpi')),
                          (fixture(title).replace('id="attachments"', 'id="removed"'), NOTICE),
                          ('<html>unavailable</html>', NOTICE)]:
            with self.assertRaises(ValueError):
                parse_notice(html, url)
        with self.assertRaises(ValueError):
            group_notices([])

    def test_inventory_expansion_and_pagination_fail_closed(self):
        html = '''<div id="cmsdip-pro-tablon-view"><button id="view:expand:1button">
        <img src="/domjava/xsp/theme/common/images/expand.gif"></button></div>'''
        self.assertEqual(inventory(html)[1], ['view:expand:1'])
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            inventory(html.replace('</div>', '<span class="xspPager">Next</span></div>'))
        with self.assertRaises(ValueError):
            inventory('<html>no listing</html>')

    def test_stalled_expansion_never_writes_partial_output(self):
        html = '''<form class="xspForm"><input name="$$viewid" value="test"></form>
        <div id="cmsdip-pro-tablon-view"><button id="expandbutton">
        <img src="/expand.gif"></button></div>'''
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.velez_rubio.requests.Session') as cls:
            response = cls.return_value.__enter__.return_value.request.return_value
            response.text, response.url = html, SOURCE
            output = Path(d) / 'proyectos.jsonl'
            with self.assertRaisesRegex(ValueError, 'stalled'):
                VelezRubioAyuntamientoAdapter().backfill_proyectos(output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
