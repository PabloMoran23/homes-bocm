"""Offline parser and complete-snapshot regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.malpartida_de_caceres import (
    ROOT, MalpartidaDeCaceresAyuntamientoAdapter, parse_instrument, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory():
    return '''<select id="PtofiguraMunicipio"><option value="368" selected>Malpartida de Cáceres</option></select>
    <a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/37118','Malpartida de Cáceres - PGM');"><img alt="Vigente">PGM - V</a>
    <a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/40484','Malpartida de Cáceres - PGM.M-001');"><img alt="Vigente">M-001 - V</a>
    <a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/35348','Malpartida de Cáceres - NNSS');"><img alt="No vigente">NNSS - NV</a>
    <a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/39826','Plan Territorial Tajo-Salor');"><img alt="Vigente">Plan territorial</a>'''


def instrument(figure_id='37118', reference='PGM', approval='30/07/2020'):
    return f'''<div id="divplaneamiento{figure_id}"><div id="infoplaneamiento{figure_id}">
    <table><tr><th>Figura urbanística</th><td>Plan General Municipal</td></tr>
    <tr><th>Ámbito territorial</th><td>Malpartida de Cáceres</td></tr>
    <tr><th>Estado</th><td>Vigente</td></tr>
    <tr><th>Referencia</th><td>{reference}</td></tr>
    <tr><th>Fecha AD</th><td>{approval}</td></tr>
    <tr><th>Fecha de publicación AD</th><td>28/10/2020</td></tr></table></div>
    <table id="tablaCalificacionplaneamientostramit"><tr><td>28/10/2020</td><td>
    <a href="https://doe.juntaex.es/pdfs/doe/2020/2090o/20AC0053.pdf">Publicación en DOE de la aprobación definitiva</a>
    </td></tr></table><div id="archivosplaneamiento{figure_id}">
    <table><tr><td>Memoria.pdf</td><td><a download="Memoria" href="/SITEX/ptofiguras/downloaddocumento/14339">PDF</a></td></tr>
    <tr><td>Plano.pdf</td><td><a download="Plano" href="/SITEX/ptofiguras/downloaddocumento/14340">PDF</a></td></tr>
    <tr><td><a href="/SITEX/ptofiguras/downloaddocumento/14339">Duplicado</a></td></tr></table></div></div>
    <a href="/SITEX/files/calificacion/FormularioAutorrellenable.pdf">Formulario de licencia</a>'''


def figure_url(figure_id='37118'):
    return ROOT + '/SITEX/ptofiguras/viewsigcat/' + figure_id


class ParserTests(unittest.TestCase):
    def test_inventory_filters_history_and_regional_plans(self):
        self.assertEqual(parse_inventory(inventory()), [figure_url(), figure_url('40484')])

    def test_wrong_municipality_or_empty_inventory_fails(self):
        for html in ['', '<h1>Formulario de licencia</h1>', inventory().replace('value="368"', 'value="369"')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_never_silently_ignored(self):
        for pagination in ['<div class="paging">2</div>', '<a rel="next" href="?page=2">Next</a>']:
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(inventory() + pagination)

    def test_instrument_groups_documents_and_preserves_dates(self):
        row = parse_instrument(instrument(), figure_url())
        self.assertEqual(row['codigo_ine'], '10115')
        self.assertEqual(row['fecha_aprob'], '2020-07-30')
        self.assertEqual(row['fecha_publicacion'], '2020-10-28')
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['source_url'], figure_url())
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertNotIn('fase', row)
        self.assertTrue(all('Formulario' not in doc['url'] for doc in row['documentos']))

    def test_documents_from_other_instruments_do_not_leak(self):
        html = instrument() + '<div id="divplaneamiento999"><a href="/SITEX/ptofiguras/downloaddocumento/999">Other plan</a></div>'
        row = parse_instrument(html, figure_url())
        self.assertFalse(any(doc['url'].endswith('/999') for doc in row['documentos']))

    def test_wrong_territory_changed_markup_and_invalid_dates_fail(self):
        for html in [instrument().replace('Malpartida de Cáceres', 'Malpartida de Plasencia'),
                     instrument().replace('Vigente', 'No vigente'),
                     instrument().replace('infoplaneamiento37118', 'removed'),
                     instrument(approval='31/02/2020'), '<h1>Login</h1>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_instrument(html, figure_url())

    def test_known_approval_conflict_is_explicit(self):
        row = parse_instrument(instrument('40938', 'PGM.PPO-001', '18/09/2026'), figure_url('40938'))
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['fechas_sitex']['fecha_aprobacion_definitiva'], '2026-09-18')
        self.assertIn('18/09/2025', row['date_warning'])
        self.assertIn('doe.juntaex.es', row['date_conflict_source_url'])

    def test_missing_dates_are_not_invented(self):
        row = parse_instrument(instrument(approval=''), figure_url())
        self.assertIsNone(row['fecha_aprob'])

    def test_snapshot_failure_does_not_replace_previous_output(self):
        adapter = MalpartidaDeCaceresAyuntamientoAdapter('malpartida-de-caceres')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'projects.jsonl'
            output.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), instrument(), '<h1>Error</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), instrument(), instrument('40484', 'PGM.M-001')]):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 2)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 2)
            self.assertFalse((Path(tmp) / 'state.json').exists())

    def test_manifest_contract_and_disabled_licences(self):
        manifest = load_manifest('malpartida-de-caceres')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('10115', 'Cáceres'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = MalpartidaDeCaceresAyuntamientoAdapter(manifest.slug)
        with patch.object(adapter, '_fetch', side_effect=AssertionError('No licence requests allowed')):
            self.assertEqual(adapter.backfill_licencias(Path('unused.jsonl'))['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
