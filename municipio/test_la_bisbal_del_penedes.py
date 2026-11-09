import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_bisbal_del_penedes import (
    ARCHIVE, SOURCE, LaBisbalDelPenedesAyuntamientoAdapter as Adapter, source_date,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def heading(text):
    return '<p class="has-background has-luminous-vivid-orange-background-color"><strong>' + text + '</strong></p>'


def page(body):
    return '<div class="entry-content"><h2>Urbanisme, la Bisbal del Penedès</h2>' + body + '</div>'


CURRENT = page(heading('MODIFICACIÓ PUNTUAL DE LES NORMES SUBSIDIÀRIES (expedient 544/2026)') + '''
<p>Es fa públic que el Ple en sessió de 30 de juliol de 2026 ha aprovat inicialment la modificació.</p>
<ul><li>Document tècnic <a href="/urbanisme/technical.pdf">Document</a></li>
<li>Publicació Butlletí Oficial de la Província 10/09/2026 <a href="/urbanisme/bopt.pdf">Document</a></li>
<li>Certificat acord 30/07/2026 <a href="/urbanisme/cert.pdf">Document</a></li></ul>
''' + heading('ACTUACIONS ANTERIORS') + f'<ul><li><a href="{ARCHIVE}">Accés a actuacions anteriors</a></li></ul>')
PREVIOUS = page(heading('APROVACIÓ INICIAL PROJECTE DE GIMNÀS I EQUIPAMENTS ESPORTIUS') + '''
<div><div><p>Es fa públic que per acord de Junta de Govern Local de 17 de juny de 2026 s’ha acordat aprovarinicialment el projecte d’obres.</p>
<ul><li>Aprovació Inicial BOPT 13 de juliol de 2026 <a href="/urbanisme/gym.pdf">Document</a></li></ul></div></div>
''' + heading('MODIFICACIÓ PUNTUAL DE LES NSS PER ADEQUAR-LES A LA NORMATIVA') + '''
<ul><li>Aprov. Inicial <a href="/urbanisme/same.pdf">PDF</a></li>
<li>Aprov. Provisional <a href="/urbanisme/same.pdf">PDF</a></li></ul>''')


class ParserTests(unittest.TestCase):
    def test_distinct_dates_and_grouped_documents(self):
        rows = Adapter.parse_inventory(CURRENT, SOURCE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '43028')
        self.assertEqual(row['expediente'], '544/2026')
        self.assertEqual(row['fecha_acuerdo'], '2026-07-30')
        self.assertEqual(row['fecha_aprob'], '2026-07-30')
        self.assertEqual(row['fecha_publicacion'], '2026-09-10')
        self.assertEqual(row['fase'], 'aprobacion_inicial')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 3)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertIsNone(row['documentos'][2]['fecha_publicacion'])

    def test_archive_boundaries_duplicates_and_uncertainty(self):
        rows = Adapter.parse_inventory(PREVIOUS, ARCHIVE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['tipo'], 'proyecto_obra_publica')
        self.assertEqual(rows[0]['fecha_acuerdo'], '2026-06-17')
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-07-13')
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(len(rows[1]['documentos'][0]['etiquetas']), 2)
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertIsNone(rows[1]['fase'])
        self.assertEqual(rows[1]['cobertura'], 'anterior')

    def test_refuses_pagination_and_empty_sources(self):
        for html in [CURRENT + '<div class="pagination"><a rel="next" href="?cursor=2">2</a></div>',
                     CURRENT + '<a href="?paged=2">2</a>',
                     page('<a href="/form.pdf">Llicències</a>'),
                     '<h1>Login</h1>',
                     page(heading('PROJECTE NOU NO RECONEGUT')),
                     page(heading('MODIFICACIÓ PUNTUAL SENSE DOCUMENTS'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html, SOURCE)

    def test_portfolio_navigation_is_not_inventory_pagination(self):
        html = CURRENT + '<div class="nav-next"><a rel="next" href="/web/portfolio/camins-i-rutes/">Fitxes Camins i Rutes</a></div>'
        self.assertEqual(len(Adapter.parse_inventory(html, SOURCE)), 1)

    def test_invalid_dates_stay_null(self):
        self.assertIsNone(source_date('Publicació 31/02/2026'))
        self.assertIsNone(source_date('/uploads/2026/09/report.pdf'))
        self.assertIsNone(source_date('juny de 2024'))
        self.assertEqual(source_date('17 de març de 2025'), '2025-03-17')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(CURRENT.replace('30 de juliol de 2026', 'juliol de 2026'), SOURCE)

    def test_complete_refresh_and_failure_preserves_output(self):
        adapter = Adapter('la-bisbal-del-penedes')
        with tempfile.TemporaryDirectory() as tmp:
            output, state = Path(tmp) / 'projects.jsonl', Path(tmp) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=[CURRENT, PREVIOUS]):
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['rows'], 3)
            saved = output.read_text()
            self.assertEqual(len([json.loads(s) for s in saved.splitlines()]), 3)
            self.assertFalse(state.exists())
            with patch.object(adapter, '_fetch', side_effect=[CURRENT, '<h1>Login</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), saved)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'lic.jsonl')['status'], 'disabled')
            self.assertEqual((Path(tmp) / 'lic.jsonl').read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('la-bisbal-del-penedes')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '43028')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)


if __name__ == '__main__':
    unittest.main()
