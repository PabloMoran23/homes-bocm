"""Deterministic semantic and pagination regression tests (no network)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.estepa import (
    INVENTORY, MODIFICATIONS, EstepaAyuntamientoAdapter,
    group_instruments, page_url, parse_inventory,
)
from municipio.manifest import load_manifest


def document(title, name, description='', date=''):
    return f'''<div class="media"><h4 class="title-element"><a href="/export/sites/estepa/es/transparencia/.galleries/IND-53-/{name}.pdf">{title}</a></h4><div class="description">{description}</div>{date}</div>'''


def block(heading, gallery, docs, narrative=''):
    return f'''<div class="contentblock"><h3>{heading}</h3><div class="contentblock-texto">{narrative}</div><section class="gallery"><h4 class="gallery-title">{gallery}</h4>{docs}</section></div>'''


def article(content):
    return '<article class="sg-indicador-trans">' + content + '</article>'


class EstepaTests(unittest.TestCase):
    def test_groups_instrument_versions_and_preserves_provenance(self):
        html = article(
            block('PLAN ESPECIAL DE PROTECCIÓN DEL CONJUNTO HISTÓRICO DE ESTEPA - APROBACIÓN DEFINITIVA', 'Memorias', document('Memoria AD', 'definitiva'))
            + block('PLAN ESPECIAL DE PROTECCIÓN DEL CONJUNTO HISTÓRICO DE ESTEPA - APROBACIÓN INICIAL', 'Planos', document('Plano AI', 'inicial'), 'Decreto 1208/22 de 23 de junio')
            + block('', '13ª MODIFICACIÓN DEL PGOU', document('Memoria', 'mod13'))
            + block('', '18ª MODIFICACION DEL PGOU', document('Memoria', 'mod18')))
        observations, _ = parse_inventory(html, INVENTORY)
        rows = {r['id']: r for r in group_instruments(observations)}
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows['estepa-plan-pepch']['documentos']), 2)
        self.assertEqual(rows['estepa-plan-pgou-mod-13']['documentos'][0]['titulo'], 'Memoria')
        self.assertTrue(rows['estepa-plan-pgou-mod-18']['documentos'][0]['url'].endswith('mod18.pdf'))
        self.assertIsNone(rows['estepa-plan-pepch']['fecha_aprob'])
        self.assertNotIn('lat', rows['estepa-plan-pepch'])

    def test_ordinance_excluded_and_publication_not_approval(self):
        html = article(block('', 'Descargas',
            document('anuncio', 'ordenanza', 'Consulta previa Ordenanza de Solares')
            + document('Documento diligenciado', 'mp15', '15ª Modificación del PGOU; aprobado definitivamente el 28 de abril de 2020', '<time datetime="2020-11-12T11:39:00">12 noviembre</time>')))
        rows = group_instruments(parse_inventory(html, MODIFICATIONS)[0])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'estepa-plan-pgou-mod-15')
        self.assertEqual(rows[0]['documentos'][0]['fecha_publicacion'], '2020-11-12')
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIn('28 de abril', rows[0]['documentos'][0]['descripcion'])

    def test_rejects_changed_empty_or_unclassified_sources(self):
        for html in ('<html>Login</html>', article(block('', 'Descargas', document('Solicitud licencia', 'form'))), article(block('', 'Desconocido', document('Documento', 'unknown')))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, INVENTORY)
        with self.assertRaises(ValueError):
            page_url(MODIFICATIONS + '?page=2')
        with self.assertRaises(ValueError):
            page_url('https://example.org/?pagegalleryfiles-1-1=2')

    def test_live_workflow_follows_all_pages_and_keeps_late_document(self):
        page2 = page_url(MODIFICATIONS + '?pagegalleryfiles-1-1=2')
        first = article(block('Plan General de Ordenación Documentación', 'PGOU del Municipio', document('Memoria', 'pgou')))
        mods = article(block('', '19ª MODIFICACIÓN DEL PGOU', document('Resumen', 'mp19')) + f'<a href="{page2}" class="pagelink">2</a>')
        last = article(block('', '19ª MODIFICACIÓN DEL PGOU', document('Planos', 'late')) + f'<a href="{MODIFICATIONS}?pagegalleryfiles-1-1=1" class="pagelink">1</a>')
        pages = {INVENTORY: first, MODIFICATIONS: mods, page2: last}
        visited = []

        class Response:
            def __init__(self, url):
                self.url = url
                self.text = pages[url]
                self.content = self.text.encode()
            def raise_for_status(self):
                pass

        def get(session, url, **kwargs):
            visited.append(url)
            return Response(url)

        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', get):
            output = Path(directory) / 'proyectos.jsonl'
            report = EstepaAyuntamientoAdapter('estepa').backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(set(visited), set(pages))
        self.assertEqual(len(visited), 3)
        self.assertEqual(report['count'], 2)
        self.assertTrue(any(doc['url'].endswith('late.pdf') for row in rows for doc in row['documentos']))

    def test_failed_pagination_does_not_write_partial_output(self):
        html = article(block('Plan General de Ordenación Documentación', 'PGOU', document('Memoria', 'pgou')) + '<a class="nextpagelink" href="?page=2">2</a>')
        with self.assertRaises(ValueError):
            parse_inventory(html, INVENTORY)

    def test_manifest(self):
        manifest = load_manifest('estepa')
        self.assertEqual((manifest.nombre, manifest.provincia), ('Estepa', 'Sevilla'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
