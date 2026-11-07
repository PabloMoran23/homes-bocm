import tempfile
import unittest
from pathlib import Path

from municipio.adapters.bargas import BargasAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def inventory(links, heading='UA – Nº 8', extra=''):
    return ('<h1>Anuncios expedientes de planeamiento y PAUs</h1>'
            '<section class="main-container"><div class="col-md-8">'
            f'<h3>{heading}</h3><ul>{links}</ul></div></section>{extra}')


def link(name, file='memoria.pdf'):
    return f'<li><a href="/wp-content/uploads/2023/11/{file}">{name}</a></li>'


class BargasTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        first = link('Proyecto de urbanización UA-8 – Memoria-1')
        html = inventory(first + first + link('Proyecto de urbanización UA-8 – Planos-1', 'planos.pdf') +
                         link('Anuncio de licitación obras de urbanización UA-8', 'anuncio.pdf'))
        rows = Adapter.parse_inventory(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['titulo'], 'Proyecto de urbanización UA-8')
        self.assertEqual(row['codigo_ine'], '45019')
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertEqual(row['id'], Adapter.parse_inventory(html.replace('2023/11', '2024/01'))[0]['id'])

    def test_procurement_and_forms_are_not_projects(self):
        for title in ('Anuncio de licitación obras de urbanización UA-8', 'Solicitud licencia de obras',
                      'Resolución ratificando selección contratista UA-8'):
            with self.subTest(title=title), self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory(link(title)))

    def test_changed_source_and_pagination_fail(self):
        good = link('Proyecto de urbanización UA-8 – Memoria-1')
        for html in ('<h1>Error</h1>', inventory(good, heading='Nueva sección'),
                     inventory(good, extra='<a rel="next" href="/pagina/2">2</a>'),
                     inventory(good, extra='<a href="?paged=2">2</a>'),
                     inventory(good.replace('UA-8', 'UA-9')),
                     inventory(good.replace('/wp-content', 'https://example.org/wp-content'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('bargas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Bargas', 'Toledo', '45019'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(Adapter('bargas').backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
