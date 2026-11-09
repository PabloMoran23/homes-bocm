"""Offline parser and complete-snapshot contract tests for Santpedor."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santpedor import SOURCE, SantpedorAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


TITLE = "Projecte d'arranjament dels carrers Pons Grau. Monjo i Plaça Sant Jordi"
URL = SOURCE + '/projecte-darranjament-dels-carrers-pons-grau-monjo-i-placa-sant-jordi'
PLAN = 'Pla de delimitació de les urbanitzacions en terrenys forestals'
PLAN_URL = SOURCE + '/pla-de-delimitacio'


def article(title, body):
    return f'<main><div id="readspeakerPage"><h1>{title}</h1>{body}</div></main>'


def inventory(entries):
    links = ''.join(f'<li><a href="{url}">{title}</a></li>' for url, title in entries)
    return article('Projectes urbanístics', f'<ul class="widgetMenu">{links}</ul>')


def detail(title=TITLE):
    return article(title, '''<div class="ddbbtext"><p>Memòria valorada de les calçades.</p>
      <a href="https://tauler.seu-e.cat/detall?idEns=819230008&amp;idEdicte=593156">Anunci</a>
      <a href="/media/projecte.pdf">Memòria del projecte</a>
      <a href="/media/projecte.pdf">Memòria del projecte</a>
      <a href="https://santpedor.webmunicipal.diba.cat/media/planols.pdf">Plànols</a></div>
      <span class="updated">Darrera actualització: 11.03.2026 | 10:47</span>''')


class SantpedorTests(unittest.TestCase):
    def test_inventory_deduplicates_responsive_menus_and_ignores_navigation(self):
        html = inventory([(URL, TITLE), (PLAN_URL, PLAN), (URL, TITLE)])
        html = html.replace('<main>', '<main><nav><a href="/tramits/llicencia">Llicència</a></nav>')
        self.assertEqual(Adapter.parse_inventory(html), [(URL, TITLE), (PLAN_URL, PLAN)])

    def test_documents_are_one_project_and_dates_have_separate_semantics(self):
        row = Adapter.parse_project(detail(), URL, TITLE)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][0]['tipo'], 'anuncio')
        self.assertEqual(row['url_documento'], 'https://www.santpedor.cat/media/projecte.pdf')
        self.assertTrue(all(d['source_url'] == URL for d in row['documentos']))
        self.assertEqual(row['fecha_actualizacion_pagina'], '2026-03-11')
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], Adapter.parse_project(detail(), URL, TITLE)['id'])

    def test_rejects_login_empty_unreviewed_or_notice_only(self):
        for html in ['<h1>Login</h1>', inventory([]), inventory([(URL, 'Sol·licitud de llicència')]),
                     inventory([('https://example.org/project', TITLE)])]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        for html in [article(TITLE, '<div class="ddbbtext"><a href="https://tauler.seu-e.cat/detall?idEdicte=1">Anunci</a></div>'),
                     detail('Unrelated news'), article(TITLE, '<p>Navigation only</p>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_project(html, URL, TITLE)

    def test_pagination_is_an_explicit_error(self):
        for control in ['<a rel="next" href="?page=2">2</a>', '<ul class="pagination"><li>2</li></ul>',
                        '<a href="?offset=20">Més</a>', '<a href="/next">Següent</a>']:
            with self.subTest(control=control), self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(inventory([(URL, TITLE)]).replace('</main>', control + '</main>'))

    def test_full_refresh_fetches_every_detail_and_preserves_output_on_failure(self):
        adapter = Adapter('santpedor')
        pages = {SOURCE: inventory([(URL, TITLE), (PLAN_URL, PLAN)]), URL: detail(), PLAN_URL: detail(PLAN)}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(fetch.call_count, 3)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(rows[1]['tipo'], 'plan_prevencion_incendios')
            old = output.read_bytes()
            pages[PLAN_URL] = '<h1>Server error</h1>'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), old)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('santpedor')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertEqual(manifest.portal.config['ine_code'], '08192')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = Adapter('santpedor').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
