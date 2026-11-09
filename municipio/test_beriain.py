import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.beriain import BeriainAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra='', title='APROBACION INICIAL ESTUDIO DETALLE 336783E', ident='27999'):
    return f'''<div id="contenido"><h2>Anuncios publicados</h2>{extra}
    <table class="gridview"><tbody><tr><td><a href="anuncio.aspx?id={ident}">Ver</a></td>
    <td>29/10/2026 - 27/11/2026</td><td>{title}</td></tr>
    <tr><td></td><td>06/11/2026 - 06/12/2026</td><td>CONCESION LICENCIA ACTIVIDAD. BAR-CAFETERIA</td></tr>
    <tr><td></td><td></td><td>LICITACION DE OBRAS</td></tr></tbody></table></div>'''


def detail(title='APROBACION INICIAL ESTUDIO DETALLE 336783E', docs=True):
    attachment = '''<div class="adjunto"><div class="adjunto-titulo">Anuncio oficial</div>
    <a class="adjunto-descargar" href="documento.aspx?id=66510&amp;modo=guardar">PDF</a></div>'''
    return f'''<div id="leer"><div class="fechas-exposicion">Expuesto actualmente desde el día 29/10/2026</div>
    <h2>{title}</h2>{attachment * 2 if docs else ''}</div>'''


class BeriainTests(unittest.TestCase):
    def test_inventory_excludes_licences_tenders_and_preserves_publication(self):
        rows = BeriainAyuntamientoAdapter.parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['expediente'], '336783E')
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-10-29')
        self.assertEqual(rows[0]['fin_exposicion'], '2026-11-27')
        docs = BeriainAyuntamientoAdapter.parse_detail(detail(), rows[0])
        self.assertEqual(len(docs), 1)
        self.assertIn('id=66510', docs[0]['url'])

    def test_reject_pagination_unknown_identity_and_changed_pages(self):
        for html in [inventory('<a href="?page=2">2</a>'),
                     inventory('<a href="javascript:__doPostBack(\'x\',\'Page$2\')">2</a>'),
                     inventory('<div class="pager">2</div>'),
                     inventory(title='ESTUDIO DE DETALLE SIN EXPEDIENTE'), '<html>Login</html>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                BeriainAyuntamientoAdapter.parse_inventory(html)
        row = BeriainAyuntamientoAdapter.parse_inventory(inventory())[0]
        for html in [detail(docs=False), detail(title='OTRO EXPEDIENTE'), detail().replace('29/10/2026', '28/10/2026')]:
            with self.assertRaises(ValueError):
                BeriainAyuntamientoAdapter.parse_detail(html, row)

    def test_group_same_instrument_and_retain_notices(self):
        first = inventory()
        second = inventory(ident='28000').split('<tbody>')[1].split('</tbody>')[0]
        html = first.replace('</table>', '<tbody>' + second + '</tbody></table>')
        def fetch(url, **kwargs):
            body = html if url == SOURCE else detail()
            response = Mock(url=url, text=body, content=b'%PDF-fixture' if 'documento.aspx' in url else body.encode())
            response.raise_for_status.return_value = None
            return response
        session = Mock()
        session.headers = {}
        session.get.side_effect = fetch
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.beriain.requests.Session') as cls:
            cls.return_value.__enter__.return_value = session
            adapter = load_portal_adapter(load_manifest('beriain'))
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(rows[0]['anuncios']), 2)
            self.assertEqual(len(rows[0]['documentos']), 1)
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertIsNone(rows[0]['fecha_acuerdo'])
            self.assertIsNone(rows[0]['geometry'])
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
