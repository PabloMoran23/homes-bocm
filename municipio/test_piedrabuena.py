import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.piedrabuena import (
    BASE, INVENTORY, PiedrabuenaAyuntamientoAdapter, group_works,
    official_url, parse_inventory, parse_work, scope,
)
from municipio.manifest import load_manifest, load_yaml


TITLE = 'El Ayuntamiento de Piedrabuena clausura el Taller + Rehabilitación de Patrimonio tras seis meses de formación y trabajo'
URL = INVENTORY + '/817-rehabilitacion'
BODY = ('Las prácticas se han desarrollado íntegramente en la Plaza de Toros de Piedrabuena. '
        'Rehabilitación, mejora y puesta en valor. 454 horas de trabajo efectivo.')


def article(title=TITLE, body=BODY, published='2026-10-01'):
    return (f'<h1 class="article-title">{title}</h1>'
            f'<time itemprop="datePublished" datetime="{published}T08:11:10+00:00"></time>'
            f'<section itemprop="articleBody">{body}</section>')


def listing(path='/817-rehabilitacion', pages=1, links=''):
    return (f'<h2 class="article-title"><a href="{INVENTORY}{path}">{TITLE}</a></h2>'
            f'<p>Página 1 de {pages}</p><ul class="pagination">{links}</ul>')


class PiedrabuenaTests(unittest.TestCase):
    def test_manifest(self):
        manifest = load_manifest('piedrabuena')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']),
                         ('Piedrabuena', 'Ciudad Real', '13063'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_inventory_and_pagination(self):
        rows, links, expected = parse_inventory(listing(pages=2, links='<a href="?start=4">Siguiente</a>'))
        self.assertEqual(rows, {URL: TITLE})
        self.assertEqual(links, [INVENTORY + '?start=4'])
        self.assertEqual(expected, 2)

    def test_empty_or_changed_inventory_fails(self):
        for html in ('<html>403</html>', '<h2 class="article-title"><a href="/other">x</a></h2>', listing().replace('Página', 'Changed')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_work_provenance_and_dates(self):
        row = parse_work(article(body=BODY + '<img src="/images/toros.jpg" alt="Foto">'), URL, scope(TITLE))
        self.assertEqual(row['fecha_publicacion'], '2026-10-01')
        self.assertIn('454 horas', row['descripcion'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], URL)
        for forbidden in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(forbidden, row)
        self.assertFalse(row['publication_ready'])

    def test_unrelated_and_procurement_not_works(self):
        for title in ('Impreso de Solicitud Licencia de Obras', 'Premio María Moliner 2026',
                      'Licitación construcción Aula de Naturaleza y Deporte',
                      'El Gobierno adjudica las obras del gimnasio', 'Exposición Museorum',
                      'Convocatoria Ayudas Rehabilitación Energética'):
            self.assertIsNone(scope(title))
        with self.assertRaises(ValueError):
            parse_work(article(body='El taller ofrece formación.'), URL, scope(TITLE))

    def test_other_two_reviewed_works(self):
        title = 'Construcción Aula de Naturaleza y Deporte'
        row = parse_work(article(title, 'Dan la bienvenido a la contrucción del Aula de Naturaleza y Deporte.', '2026-08-10'), URL, scope(title))
        self.assertEqual(row['id'], 'piedrabuena-aula-naturaleza-deporte-2026')
        title = 'El Ayuntamiento de Piedrabuena inicia las obras para renovar redes de abastecimiento de agua en cinco nuevas calles'
        row = parse_work(article(title, 'Ha comenzado las obras: Eloy Gonzalo, Mónico Sánchez, Serna, General Sabariego y Castillo.', '2022-03-11'), URL, scope(title))
        self.assertEqual(row['fecha_publicacion'], '2022-03-11')

    def test_group_documents_and_distinguish_cycles(self):
        first = parse_work(article(), URL, scope(TITLE))
        second = parse_work(article(published='2026-10-02'), URL + '-2', scope(TITLE))
        third = parse_work(article(published='2027-10-01'), URL + '-3', scope(TITLE))
        rows = group_works([second, first, third, second])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-10-01')
        self.assertEqual(rows[0]['documentos'][1]['fecha_publicacion'], '2026-10-02')

    def test_host_guard(self):
        with self.assertRaises(ValueError):
            official_url('https://example.org/817-example')
        self.assertEqual(official_url('https://www.piedrabuena.es/test#frag'), BASE + '/test')

    def test_crawler_follows_all_pages_and_groups(self):
        next_url = INVENTORY + '?start=4'
        pages = {INVENTORY: listing(pages=2, links='<a href="?start=4">Siguiente</a>'),
                 next_url: listing('/818-rehabilitacion', 2),
                 URL: article(), INVENTORY + '/818-rehabilitacion': article(published='2026-10-02')}
        adapter = PiedrabuenaAyuntamientoAdapter('piedrabuena')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda session, url: pages[url]) as fetch:
            path = Path(tmp) / 'out.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['archive_pages'], 2)
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(json.loads(path.read_text())['documentos']), 2)
            self.assertEqual(fetch.call_count, 4)

    def test_incomplete_or_repeated_pages_preserve_output(self):
        adapter = PiedrabuenaAyuntamientoAdapter('piedrabuena')
        for html in (listing(pages=2), listing(pages=2, links='<a href="?start=4">Siguiente</a>')):
            with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=html):
                path = Path(tmp) / 'out.jsonl'
                path.write_text('previous successful output')
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous successful output')

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = PiedrabuenaAyuntamientoAdapter('piedrabuena').backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
