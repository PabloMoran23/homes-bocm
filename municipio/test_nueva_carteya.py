import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.nueva_carteya import (
    SOURCE, NuevaCarteyaAyuntamientoAdapter, parse_inventory, parse_project,
)


def inventory(title='Inauguración Gimnasio Municipal', pagination=''):
    return '<main><h2><a href="/noticias/340-gimnasio.html">' + title + '</a></h2>' + pagination + '</main>'


def article(text):
    return '''<article class="uk-article"><h1>Inauguración Gimnasio Municipal</h1>
    <div class="tm-article-content">''' + text + '''
    <a href="/images/memoria.pdf">Memoria</a><a href="/images/memoria.pdf">Duplicado</a>
    <img src="/images/obra.jpg"><div class="css_buttons1">Tweet</div></div></article>'''


class NuevaCarteyaTests(unittest.TestCase):
    def test_selects_works_not_forms_or_unrelated_news(self):
        for title in ['URBANISMO', 'Declaración responsable de ejecución de obras',
                      'Convenio Proyecto Hombre', 'Licitación del Gimnasio', 'Inauguración Feria del Libro']:
            self.assertEqual(parse_inventory(inventory(title), SOURCE)[0], {})
        self.assertEqual(len(parse_inventory(inventory(), SOURCE)[0]), 1)

    def test_grouped_documents_without_fabricated_dates(self):
        row = parse_project(article('El martes 24 de junio tuvo lugar la inauguración oficial del Gimnasio Municipal.'),
                            SOURCE + '/340', [SOURCE])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['imagenes'], ['https://aytonuevacarteya.es/images/obra.jpg'])
        self.assertNotIn('Tweet', row['descripcion'])
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon']:
            self.assertNotIn(key, row)

    def test_invitation_is_not_completed_work(self):
        self.assertIsNone(parse_project(article('Quedáis invitados a la inauguración el 30 de junio.'), SOURCE, []))

    def test_pagination_follows_last_and_nonconsecutive_links(self):
        p = '<ul class="uk-pagination"><li><a href="?start=184">Última</a></li></ul>'
        found, pages = parse_inventory(inventory(pagination=p), SOURCE)
        self.assertEqual(pages, {SOURCE + '?start=184'})
        pages_html = {SOURCE: inventory(pagination=p), SOURCE + '?start=184': inventory('Fin de archivo').replace('340-gimnasio', '1-archivo')}
        target = next(iter(found))
        pages_html[target] = article('Tuvo lugar la inauguración oficial del Gimnasio Municipal.')
        adapter = NuevaCarteyaAyuntamientoAdapter('nueva-carteya')
        with TemporaryDirectory() as d, patch.object(adapter, '_fetch', side_effect=lambda session, url: pages_html[url]):
            out = Path(d) / 'rows.jsonl'
            report = adapter.backfill_proyectos(out)
            self.assertEqual(report['inventory_pages'], 2)
            self.assertEqual(len(out.read_text().splitlines()), 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '14046')

    def test_changed_or_repeated_inventory_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<main>Empty</main>', SOURCE)
        bad = '<ul class="uk-pagination"><a href="https://example.org/">Next</a></ul>'
        with self.assertRaises(ValueError):
            parse_inventory(inventory(pagination=bad), SOURCE)
        repeated = inventory(pagination='<ul class="uk-pagination"><a href="?start=8">2</a></ul>')
        adapter = NuevaCarteyaAyuntamientoAdapter('nueva-carteya')
        with TemporaryDirectory() as d, patch.object(adapter, '_fetch', return_value=repeated):
            out = Path(d) / 'rows.jsonl'
            out.write_text('previous successful output')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous successful output')


if __name__ == '__main__':
    unittest.main()
