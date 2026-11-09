import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.llica_de_vall import (
    SOURCE, WATER_FINAL, WATER_INITIAL, LlicaDeVallAyuntamientoAdapter,
    exact_date, group_projects, parse_detail, parse_inventory, supported,
)
from municipio.manifest import load_manifest
from municipio.entity_policy import classify

TITLE = 'Projecte executiu de reforma de la cuina de l’escola'
URL = SOURCE + '/cuina.html'


def inventory(entries, pages=()):
    return '<main><h1>Urbanisme</h1>' + ''.join(
        f'<div class="tplDefault"><a href="{u}"><p>{t}</p></a></div>' for u, t in entries
    ) + ''.join(f'<a href="{u}">2</a>' for u in pages) + '</main>'


def detail(text='', title=TITLE, docs=('one.pdf', 'two.pdf')):
    return '<main><div class="containerArticle"><h1>' + title + '</h1><div class="ddbbtext">' + text + '</div><span class="updated">Darrera actualització: 14.07.2026</span></div><section id="page-documents">' + ''.join(
        f'<a href="/media/repository/{d}">{d}</a>' for d in docs
    ) + '</section></main>'


class LlicaDeVallTests(unittest.TestCase):
    def test_manifest(self):
        m = load_manifest('llica-de-vall')
        self.assertEqual(m.provincia, 'Barcelona')
        self.assertEqual(m.portal.config['ine_code'], '08108')
        self.assertFalse(m.licencias.enabled)

    def test_dates_documents_and_missing_geometry(self):
        row = parse_detail(detail('Aprovació inicial: 29 d’abril de 2026<br>Aprovació definitiva: 13 de juliol de 2026'), URL, TITLE)
        self.assertEqual(row['fecha_aprob'], '2026-07-13')
        self.assertEqual(row['eventos_fuente'][0]['fecha'], '2026-04-29')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertEqual(classify(row)['entity_type'], 'documento')
        self.assertFalse(classify(row)['activity_eligible'])
        self.assertIsNone(parse_detail(detail(), URL, TITLE)['fecha_aprob'])

    def test_certificate_and_conditional_dates_not_approval_dates(self):
        text = 'Aprovació definitiva: al no presentar-se cap al·legació, aprovat per acord de 20/07/2026, i així ho certifica la Secretària en data 22/09/2026.'
        row = parse_detail(detail(text), URL, TITLE)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIn('22/09/2026', row['descripcion'])
        self.assertIsNone(exact_date('20 de juny de 2023 (supeditada amb prescripcions)'))
        self.assertIsNone(exact_date('31/02/2026'))
        self.assertEqual(exact_date('22 de setembre del 2022'), '2022-09-22')

    def test_excludes_unrelated_records(self):
        for title in ['Sol·licitud de llicència d’obres', 'Aprovació dels estatuts de la junta de compensació', 'Ordenança Municipal', 'Notícia sobre una licitació', 'Text refós PGOM Lliçà de Vall']:
            self.assertFalse(supported(title))
        self.assertTrue(supported('Modificació puntual del Pla General'))
        self.assertTrue(supported('Memòria valorada per a les obres del parc'))

    def test_rejects_changed_sources(self):
        with self.assertRaises(ValueError):
            parse_inventory('<main><h1>Login</h1></main>')
        with self.assertRaises(ValueError):
            parse_detail(detail(docs=()), URL, TITLE)
        with self.assertRaises(ValueError):
            parse_detail(detail(title='Notícia'), URL, TITLE)
        with self.assertRaises(ValueError):
            parse_inventory(inventory([(URL, TITLE)], [SOURCE + '?pag=2&other=1']))

    def test_water_versions_grouped_with_all_documents(self):
        rows = [parse_detail(detail('Aprovació inicial: 21/10/2024', docs=('initial.pdf',)), WATER_INITIAL, TITLE),
                parse_detail(detail(docs=('definitive.pdf',)), WATER_FINAL, TITLE)]
        grouped = group_projects(rows)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]['documentos']), 2)
        self.assertEqual(len(grouped[0]['source_urls']), 2)
        self.assertEqual(grouped[0]['eventos_fuente'][0]['fecha'], '2024-10-21')
        self.assertEqual(group_projects(list(reversed(rows)))[0]['id'], grouped[0]['id'])

    def test_follows_pagination_and_refreshes_snapshot(self):
        second = SOURCE + '?pag=2'
        other = SOURCE + '/other.html'
        pages = {SOURCE: inventory([(URL, TITLE)], [second]),
                 second: inventory([(other, TITLE)]), URL: detail(), other: detail()}
        adapter = LlicaDeVallAyuntamientoAdapter('llica-de-vall')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            path = Path(folder) / 'projects.jsonl'
            result = adapter.update_proyectos(path, Path(folder) / 'state.json')
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)
            self.assertEqual(fetch.call_count, 4)

    def test_repeated_pagination_aborts_without_overwriting(self):
        html = inventory([(URL, TITLE)], [SOURCE + '?pag=2'])
        adapter = LlicaDeVallAyuntamientoAdapter('llica-de-vall')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', return_value=html):
            path = Path(folder) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'Repeated inventory'):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
