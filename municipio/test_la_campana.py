"""Offline semantic and traversal regression tests; no network required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from municipio.adapters.la_campana import SOURCE, LaCampanaAyuntamientoAdapter, parse_page
from municipio.manifest import load_manifest

NOTICE = '/images/Anuncios/OBRAS-SERVICIOS/Avisos_Obras/calle.jpg'


def article(text, notice=NOTICE):
    return (f'<div itemprop="blogPost"><p>19/10/2017</p>'
            f'<p>INFORMACIÓN MUNICIPAL</p><p>{text}</p>'
            f'<a href="{notice}"><img alt="Aviso de obras"></a></div>')


WORK = article('El próximo día 20 de octubre de 2017 darán comienzo las obras de mejoras de las calles Nueva, Perdiz y Tenería. Disculpen las molestias.')


def page(content=WORK, n=1, total=1, next_url=None):
    following = f'<li class="pagination-next"><a href="{next_url}">Siguiente</a></li>' if next_url else ''
    return (f'<div class="blog">{content}<div class="pagination">'
            f'<p class="counter">Página {n} de {total}</p>{following}</div></div>')


def response(html, url=SOURCE):
    return SimpleNamespace(text=html, content=html.encode(), url=url, raise_for_status=lambda: None)


class LaCampanaTests(unittest.TestCase):
    def test_real_notice_semantics_and_provenance(self):
        rows, following, _, _ = parse_page(page(), SOURCE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['fecha_publicacion'], '2017-10-19')
        self.assertIn('20 de octubre de 2017', row['descripcion'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '41022')
        self.assertEqual(row['documentos'][0]['url'], row['url'])
        self.assertIsNone(following)

    def test_forms_tenders_and_service_announcements_are_excluded(self):
        excluded = ''.join(article(t) for t in [
            'Solicitud de licencia de obras en calle Nueva.',
            'REUNIÓN INFORMATIVA SOBRE LA ADJUDICACIÓN DE OBRAS EN EL P.I. EL CRUCE',
            'PLAN ESPECIAL DE TRÁFICO Y LIMPIEZA VIARIA PARA LA SEMANA SANTA 2017',
            'CALLE JILGUERO CORTADA PROVISIONALMENTE POR OBRAS',
            'Comienzo del servicio de recogida de basuras.',
        ])
        self.assertEqual(parse_page(page(excluded), SOURCE)[0], [])

    def test_navigation_is_not_project_and_missing_notice_fails(self):
        rows = parse_page('<nav>' + WORK + '</nav>' + page(article('Sin obra')), SOURCE)[0]
        self.assertEqual(rows, [])
        with self.assertRaises(ValueError):
            parse_page(page(WORK.replace(NOTICE, '/solicitud.pdf')), SOURCE)
        with self.assertRaises(ValueError):
            parse_page('<a href="/obra.pdf">Obra</a>', SOURCE)

    def test_complete_traversal_deduplicates_and_retains_links(self):
        second = SOURCE + '?start=6'
        with TemporaryDirectory() as directory, patch('municipio.adapters.la_campana.requests.get') as get:
            get.side_effect = [response(page(n=1, total=2, next_url=second)), response(page(n=2, total=2), second)]
            output = Path(directory) / 'proyectos.jsonl'
            report = LaCampanaAyuntamientoAdapter().backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(report['pages'], 2)
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]['source_urls']), {SOURCE, second})
            self.assertEqual(get.call_count, 2)

    def test_partial_pagination_fails_without_overwriting_output(self):
        with TemporaryDirectory() as directory, patch('municipio.adapters.la_campana.requests.get') as get:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            get.return_value = response(page(n=1, total=2))
            with self.assertRaises(ValueError):
                LaCampanaAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')
        with self.assertRaises(ValueError):
            parse_page(page(n=1, total=2, next_url='https://example.org/'), SOURCE)

    def test_pagination_cycle_fails(self):
        with TemporaryDirectory() as directory, patch('municipio.adapters.la_campana.requests.get') as get:
            get.return_value = response(page(n=1, total=2, next_url=SOURCE))
            with self.assertRaisesRegex(ValueError, 'cycle'):
                LaCampanaAyuntamientoAdapter().backfill_proyectos(Path(directory) / 'p.jsonl')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('la-campana')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.la_campana:LaCampanaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
