"""Offline parser/coverage checks; fixtures reproduce the observed BOP structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.aguilar_de_la_frontera import (
    AguilarDeLaFronteraAyuntamientoAdapter, ISSUER, SEARCH,
    group_plans, parse_search, plan_identity,
)
from municipio.manifest import load_manifest, load_yaml


def item(title, identifier='2014-779', day='19-02-2014', issuer=ISSUER):
    return (f'<li class="announcement"><h3>{issuer}</h3><p>{title}</p>'
            f'<p><a class="pdf" href="/visor-pdf/{day}/BOP-A-{identifier}.pdf">PDF</a></p></li>')


def page(items, total=None):
    count = len(items)
    return f'<div>Resultados del 1 al {count} de {count if total is None else total}</div><ul>{"".join(items)}</ul>'


FIRST = 'Anuncio por el que se somete a información pública el Plan Parcial, correspondiente al sector residencial 22, tras la Modificación del PGOU (Cerro Romano y su entorno)'
SECOND = 'Notificación aprobación inicial Plan Parcial SR-22 de desarrollo del PGOU de Aguilar de la Frontera'


class ParserTests(unittest.TestCase):
    def test_group_same_instrument_keep_publication_provenance(self):
        docs, total = parse_search(page([item(FIRST), item(SECOND, '2014-1437', '18-03-2014')]), SEARCH)
        rows = group_plans(docs)
        self.assertEqual(total, 2)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['sector'], 'SR-22')
        self.assertEqual([d['fecha_publicacion'] for d in row['documentos']], ['2014-02-19', '2014-03-18'])
        self.assertEqual(row['fecha_publicacion'], '2014-03-18')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertNotIn('fase', row)
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '14002')
        self.assertTrue(all(d['emisor'] == ISSUER and d['inventory_url'] == SEARCH for d in row['documentos']))

    def test_exclude_forms_procurement_and_incidental_mentions(self):
        for title in [
            'Modelo solicitud licencia Plan Parcial SR-22',
            'Licitación para aprobación del Plan Parcial SR-22',
            'Bases de oposición: información pública Plan Parcial SR-22',
            'Aprobación definitiva del Estudio de Detalle del Plan Parcial UE PP SR-4',
            'Información pública Proyecto de Reparcelación del Plan Parcial SI-II',
            'Aprobación Ordenanza reguladora del Plan Parcial SR-22',
            'Fiestas y actividades deportivas',
        ]:
            with self.subTest(title=title):
                self.assertIsNone(plan_identity(title))

    def test_modification_is_separate_from_base_plan_and_other_sector(self):
        titles = ['Aprobación definitiva Plan Parcial SR-16',
                  'Información pública modificación Plan Parcial SR-16 del PGOU',
                  'Información pública modificación Plan Parcial SR-17 del PGOU',
                  'Información pública modificación Plan Parcial SR-16 de alineaciones']
        docs, _ = parse_search(page([item(t, f'2014-{i}') for i, t in enumerate(titles)]), SEARCH)
        self.assertEqual(len(group_plans(docs)), 4)

    def test_reject_wrong_municipality_and_document_host(self):
        with self.assertRaisesRegex(ValueError, 'issuer'):
            parse_search(page([item(FIRST, issuer='Ayuntamiento de Córdoba')]), SEARCH)
        with self.assertRaisesRegex(ValueError, 'document URL'):
            parse_search(page([item(FIRST).replace('href="/visor', 'href="https://example.org/visor')]), SEARCH)

    def test_unidentified_named_plan_fails_instead_of_silent_omission(self):
        with self.assertRaisesRegex(ValueError, 'sector'):
            plan_identity('Aprobación definitiva Plan Parcial nuevo sector sin número')

    def test_empty_changed_and_inconsistent_markup(self):
        for html in ['<h1>Access denied</h1>', page([item(FIRST)]).replace('al 1', 'al 2')]:
            with self.assertRaises(ValueError):
                parse_search(html, SEARCH)
        empty = '<div>No se encontraron datos para los criterios de búsqueda especificados indicados.</div>'
        self.assertEqual(parse_search(empty, SEARCH), ([], 0))
        with self.assertRaisesRegex(ValueError, 'No genuine'):
            group_plans([])

    def test_date_is_from_publication_path_not_announcement_year(self):
        docs, _ = parse_search(page([item('Información pública modificación Plan Parcial SR-16', '2011-9935', '22-11-2013')]), SEARCH)
        self.assertEqual(docs[0]['fecha_publicacion'], '2013-11-22')

    def test_manifest_and_dynamic_loader_spec(self):
        manifest = load_manifest('aguilar-de-la-frontera')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '14002')
        self.assertEqual(manifest.provincia, 'Córdoba')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        from municipio.adapters.registry import load_portal_adapter
        self.assertIsInstance(load_portal_adapter(manifest), AguilarDeLaFronteraAyuntamientoAdapter)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.adapter = AguilarDeLaFronteraAyuntamientoAdapter('aguilar-de-la-frontera')

    def response(self, html):
        return Mock(text=html, content=html.encode(), url=SEARCH)

    def test_exhaust_saturated_search_and_check_total(self):
        a = item('Aprobación definitiva Plan Parcial SR-15', '2016-1626', '26-05-2016')
        b = item('Aprobación definitiva Plan Parcial SI-11', '2012-1047', '21-02-2012')
        responses = [self.response(page([a], total=2)), self.response(page([a], total=2)),
                     self.response(page([b])), self.response(page([a]))]
        with patch.object(self.adapter, '_get', side_effect=responses) as get:
            notices, urls = self.adapter._inventory(lambda *args: None)
        self.assertEqual(len(notices), 2)
        self.assertEqual(len(urls), 4)
        self.assertIn('fechaIni', get.call_args_list[-1].args[1])

    def test_missing_result_during_pagination_fails(self):
        a = item(FIRST)
        responses = [self.response(page([a], total=2)), self.response(page([a]))]
        with patch.object(self.adapter, '_get', side_effect=responses):
            with self.assertRaisesRegex(ValueError, 'unaccounted'):
                self.adapter._inventory(lambda *args: None)

    def test_document_failure_does_not_replace_existing_snapshot(self):
        docs, _ = parse_search(page([item(FIRST)]), SEARCH)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch.object(self.adapter, '_inventory', return_value=(docs, [SEARCH])), patch.object(self.adapter, '_get', return_value=Mock(content=b'<html>blocked</html>')):
                with self.assertRaisesRegex(ValueError, 'not a PDF'):
                    self.adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_update_refreshes_complete_snapshot_and_licences_disabled(self):
        docs, _ = parse_search(page([item(FIRST)]), SEARCH)
        pdf = Mock(content=b'%PDF-1.7\nfixture', headers={'Content-Type': 'application/pdf'})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'projects.jsonl'
            with patch.object(self.adapter, '_inventory', return_value=(docs, [SEARCH])), patch.object(self.adapter, '_get', return_value=pdf):
                result = self.adapter.update_proyectos(output, Path(folder) / 'state.json')
            row = json.loads(output.read_text())
            self.assertEqual(result['documents'], 1)
            self.assertEqual(len(row['documentos'][0]['sha256']), 64)
            self.assertTrue(self.adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
