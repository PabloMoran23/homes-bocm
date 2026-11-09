"""Offline semantic and pagination regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pozuelo_de_calatrava import (
    BASE, PozueloDeCalatravaAyuntamientoAdapter, group_projects,
    parse_article, parse_inventory, publication_date, subject,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

TITLE = 'El Ayuntamiento de Pozuelo de Calatrava da el pistoletazo de salida a las obras del nuevo pabellón deportivo municipal'
SECOND = 'El Pleno de Pozuelo de Calatrava aprueba por unanimidad que el nuevo polideportivo municipal lleve el nombre de Eusebio Angulo'
URL = BASE + 'actualidad/2361/pabellon'


def article(title=TITLE, body='El Ayuntamiento ha firmado hoy el acta de replanteo que supone el inicio oficial de las obras.', published='15.enero.2026'):
    return f'''<div class="listado noticia"><h2>{title}</h2>
    <div class="datosNoticia"><div class="fecha"><p class="f">{published}</p></div></div>
    <p>{body}</p><div class="documentosAdjuntos">
    <a href="/ARCHIVO/documentos/pabellon.pdf">Proyecto</a>
    <a href="/ARCHIVO/fotografias/noticias/obra.jpeg">Foto</a>
    <a href="https://other.example/foreign.pdf">Foreign</a></div></div>'''


def inventory(page=1, next_page=2, title=TITLE, link=URL):
    controls = f'<div onclick="fncPaginacion({next_page});">ANTERIOR</div>' if next_page else '<div class="off">ANTERIOR</div>'
    return f'''<form name="frmPaginacion" action="actualidad.php">
    <input name="p" value="{page}"><input name="d" value="20260101">
    <input name="h" value="20261231"></form>
    <div class="listado"><div class="noticiaListado"><h2><a href="{link}">{title}</a></h2></div></div>
    <div class="barraPag">{controls}</div>
    <aside><a href="/actualidad/999/irrelevant">Sidebar</a></aside>'''


class ParserTests(unittest.TestCase):
    def test_pagination_uses_numbers_not_direction_label(self):
        url = BASE + 'actualidad.php?d=20260101&h=20261231&p=1'
        items, nxt = parse_inventory(inventory(), url)
        self.assertEqual(items, [(TITLE, URL)])
        self.assertIn('p=2', nxt)
        self.assertIn('d=20260101', nxt)
        _, nxt = parse_inventory(inventory(2, 1), url.replace('p=1', 'p=2'))
        self.assertIsNone(nxt)

    def test_missing_or_ignored_pagination_fails(self):
        url = BASE + 'actualidad.php?d=20260101&h=20261231&p=1'
        for html in ('<h1>Captcha</h1>', inventory(2), inventory(next_page=3),
                     inventory().replace('fncPaginacion(2);', 'unknown()')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, url)

    def test_grouping_dates_and_attachment_provenance(self):
        first = parse_article(article(), URL, TITLE)
        second_url = BASE + 'actualidad/2400/nombre'
        second = parse_article(article(SECOND, 'Las obras están actualmente en ejecución.', '2.junio.2026'), second_url, SECOND)
        rows = group_projects([second, first, first], 'inventory')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['titulo'], TITLE)
        self.assertEqual(row['fecha_publicacion'], '2026-01-15')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['fecha_publicacion'], '2026-06-02')
        self.assertEqual(len(row['documentos'][0]['adjuntos']), 2)
        self.assertEqual(row['documentos'][1]['adjuntos'][0]['source_url'], second_url)
        for key in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])

    def test_rejects_forms_procurement_and_unrelated_news(self):
        for title in ('Solicitud licencia de obras', 'Abre la licitación del nuevo pabellón deportivo municipal',
                      'Adjudica las obras del nuevo pabellón deportivo municipal',
                      'BASES del programa de empleo', 'Certamen de pintura y sus obras',
                      'La Junta aprueba la licencia para 27 viviendas'):
            self.assertIsNone(subject(title))
        self.assertIsNone(parse_article(article(body='Está prevista la futura construcción.'), URL, TITLE))
        with self.assertRaises(ValueError):
            parse_article(article(), URL, 'Changed title')
        with self.assertRaises(ValueError):
            group_projects([], 'inventory')

    def test_date_semantics(self):
        self.assertEqual(publication_date('26 febrero, 2026'), '2026-02-26')
        for text in ('2026', '31.febrero.2026'):
            with self.assertRaises(ValueError):
                publication_date(text)

    def test_manifest(self):
        manifest = load_manifest('pozuelo-de-calatrava')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), PozueloDeCalatravaAyuntamientoAdapter)

    def test_live_path_follows_all_pages_and_writes_only_on_success(self):
        class Response:
            def __init__(self, url, text):
                self.url, self.text = url, text
            def raise_for_status(self):
                pass
        adapter = PozueloDeCalatravaAyuntamientoAdapter('pozuelo-de-calatrava')
        def get(url, **kwargs):
            if '/actualidad/2361/' in url:
                return Response(url, article())
            if 'p=2' in url:
                return Response(url, inventory(2, 1, 'Unrelated event', BASE + 'actualidad/999/event'))
            return Response(url, inventory())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.pozuelo_de_calatrava.requests.get', side_effect=get):
            path = Path(tmp) / 'works.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['archive_pages'], 2)
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '13066')
            previous = path.read_text()
            with patch('municipio.adapters.pozuelo_de_calatrava.requests.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), previous)


if __name__ == '__main__':
    unittest.main()
