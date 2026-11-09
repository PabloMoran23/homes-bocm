import json
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.villanueva_del_rio_segura import (
    BASE, INVENTORY, VillanuevaDelRioSeguraAyuntamientoAdapter,
    group_notices, parse_inventory, parse_notice,
)

TITLE = 'Plan General Municipal de Ordenación de Villanueva del Río Segura'


def inventory(offset, href, following=''):
    return (f'<article class="uk-article"><h1 class="uk-article-title"><a href="{href}">{TITLE}</a></h1></article>'
            f'<ul class="uk-pagination">{following}</ul><!--{offset}-->')


def notice(body):
    return f'<article class="uk-article"><h1 class="uk-article-title">{TITLE}</h1>{body}</article>'


class ParserTests(unittest.TestCase):
    def test_group_documents_dates_and_provenance(self):
        old = parse_notice(notice('<p>sesión celebrada del 27.07.17, ha aprobado la subsanación</p>'
                                 '<a href="/PGMO/mapa.pdf">Plano</a>'), BASE + '/index.php/174-old')
        new = parse_notice(notice('<p>Orden de fecha 23 de junio de 2022, relativa a aprobación definitiva parcial</p>'
                                 '<a href="/PGMO/mapa.pdf">Plano</a><a href="/PGMO/mapa.pdf">Copia</a>'
                                 '<a href="https://www.borm.es/services/anuncio/ano/2022/numero/3568/pdf?id=808916">Orden</a>'),
                           BASE + '/index.php/295-new')
        row, = group_notices([old, new])
        self.assertEqual(row['fecha_aprob'], '2022-06-23')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(old['fecha_aprob'])
        self.assertEqual(old['fecha_acuerdo'], '2017-07-27')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['procedencias']), 2)
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '30042')

    def test_inventory_rejects_unrelated_and_bad_pagination(self):
        html = inventory(0, '/index.php/295-plan')
        rows, _ = parse_inventory(html.replace(TITLE, 'Solicitud de licencia de obras'))
        self.assertEqual(rows, {})
        with self.assertRaises(ValueError):
            parse_inventory(html + '<ul class="uk-pagination"><a href="?page=2">Siguiente</a></ul>')
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service unavailable</html>')
        with self.assertRaises(ValueError):
            parse_notice(notice('<a href="/solicitud.pdf">Formulario</a>'), BASE)

    def test_live_path_follows_all_pages_and_discovers_details(self):
        pages = {
            INVENTORY: inventory(0, '/index.php/295-plan', '<a href="?start=5">2</a><a href="?start=10">Final</a>'),
            INVENTORY + '?start=5': inventory(5, '/index.php/295-plan', '<a href="?start=10">3</a>'),
            INVENTORY + '?start=10': inventory(10, '/index.php/174-old', '<a href="?limitstart=0">Inicio</a>'),
            BASE + '/index.php/295-plan': notice('<p>de fecha 23 de junio de 2022, relativa a aprobación definitiva parcial</p><a href="/PGMO/norma.pdf">Normas</a>'),
            BASE + '/index.php/174-old': notice('<a href="/PGMO/plano.pdf">Plano</a>'),
        }
        adapter = VillanuevaDelRioSeguraAyuntamientoAdapter('villanueva-del-rio-segura')
        visited = []
        def fetch(url):
            visited.append(url)
            return pages[url]
        adapter._fetch = fetch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['inventory_pages'], 3)
            self.assertEqual(len(visited), 5)
            self.assertEqual(len(json.loads(path.read_text())['documentos']), 2)
            original = path.read_text()
            pages[INVENTORY + '?start=5'] = '<html>Broken</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), original)
        self.assertEqual(adapter.backfill_licencias(Path('/unused'))['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
