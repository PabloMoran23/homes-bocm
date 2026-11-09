"""Offline parser and extraction contract tests; no network or external fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.fregenal_de_la_sierra import (
    FregenalDeLaSierraAyuntamientoAdapter, INVENTORY, LANDING, NAME,
    municipality_id, parse_figure, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

URL = 'https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40684'
SELECTOR = '<select id="PtofiguraMunicipio"><option value="75">Fregenal de la Sierra</option></select>'
TREE = '''<ul id="listaplaneamientosnuevaley">
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/38282','Plan Territorial de Tentudía-Sierra Suroeste');">Territorial</a></ul>
<ul id="listaplaneamientosantigualey">
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/40684','Fregenal de la Sierra - NNSS.R-001.M-042');">M-042</a>
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/40684','Fregenal de la Sierra - NNSS.R-001.M-042');">duplicado</a></ul>'''
FIGURE = '''<div id="content"><h1>Normas Subsidiarias, revisión 001, modificación 042</h1>
<table class="juntaex">
<tr><th>Figura urbanística</th><td>Modificación puntual n.º 38 para redefinir Reformas</td></tr>
<tr><th>Ámbito territorial</th><td>Fregenal de la Sierra</td><td style="display:none">75</td></tr>
<tr><th>Referencia</th><td>NNSS.R-001.M-042</td></tr>
<tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Fecha AD</th><td>24/03/2025</td></tr>
<tr><th>Fecha de publicación AD</th><td>25/04/2025</td></tr></table>
<table id="tablaCalificacionplaneamientostramit"><tbody>
<tr><th>Fecha del trámite</th><th>Trámite</th></tr>
<tr><td>02/04/2024</td><td>Aprobación inicial</td></tr>
<tr><td>25/04/2025</td><td><a href="https://doe.juntaex.es/a.pdf">Publicación en DOE de la aprobación definitiva</a></td></tr>
</tbody></table>
<div id="archivosplaneamiento40684"><table><tr><td>memoria.pdf</td><td><a download="Memoria justificativa - memoria.pdf" href="/SITEX/ptofiguras/downloaddocumento/12338">PDF</a></td></tr></table></div>
</div><a href="/unrelated-news">Not a project document</a>'''


class ParserTests(unittest.TestCase):
    def test_selector_and_inventory_deduplication(self):
        self.assertEqual(municipality_id(SELECTOR), '75')
        urls, excluded = parse_inventory(TREE)
        self.assertEqual(urls, [URL])
        self.assertEqual(len(excluded), 1)

    def test_no_static_municipality_or_fallback_records(self):
        for html in ('', SELECTOR.replace(NAME, 'Otra población'), SELECTOR + SELECTOR):
            with self.assertRaises(ValueError):
                municipality_id(html)
        with self.assertRaises(ValueError):
            parse_inventory('<a href="/licencia.pdf">Solicitud licencia de obra</a>')

    def test_changed_or_paged_inventory_fails(self):
        for html in (TREE + '<div class="pagination">2</div>', TREE.replace('addTab(', 'other(')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_dates_documents_and_identity(self):
        row = parse_figure(FIGURE, URL)
        self.assertEqual(row['fecha_aprob'], '2025-03-24')
        self.assertEqual(row['fecha_publicacion'], '2025-04-25')
        self.assertEqual(row['expediente'], 'NNSS.R-001.M-042')
        self.assertIn('38', row['titulo'])  # registry reference and municipal number differ
        self.assertEqual(row['tramites'][0]['fecha'], '2024-04-02')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['source_url'] == URL for d in row['documentos']))
        self.assertEqual(row['codigo_ine'], '06050')
        self.assertNotIn('fase', row)
        self.assertNotIn('lat', row)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertFalse(row['publication_ready'])

    def test_registry_heading_used_when_description_is_blank(self):
        row = parse_figure(FIGURE.replace('Modificación puntual n.º 38 para redefinir Reformas', ''), URL)
        self.assertEqual(row['titulo'], 'Normas Subsidiarias, revisión 001, modificación 042')

    def test_missing_dates_are_not_inferred_from_events(self):
        row = parse_figure(FIGURE.replace('<td>24/03/2025</td>', '<td></td>'), URL)
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(len(row['tramites']), 2)

    def test_wrong_municipality_missing_title_and_invalid_dates_fail(self):
        for html in (FIGURE.replace(NAME, 'Otro municipio'),
                     FIGURE.replace('Modificación puntual n.º 38 para redefinir Reformas', '').replace('<h1>Normas Subsidiarias, revisión 001, modificación 042</h1>', ''),
                     FIGURE.replace('24/03/2025', '31/02/2025'), '<html>Access denied</html>'):
            with self.assertRaises(ValueError):
                parse_figure(html, URL)

    def test_documents_do_not_leak_between_figures(self):
        parse_figure(FIGURE, URL)
        row = parse_figure(FIGURE.replace('id="archivosplaneamiento40684"', 'id="unrelated"')
                          .replace('id="tablaCalificacionplaneamientostramit"', 'id="unrelated2"'), URL)
        self.assertEqual(row['documentos'], [])

    def test_manifest(self):
        manifest = load_manifest('fregenal-de-la-sierra')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('06050', 'Badajoz'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_live_flow_uses_post_and_never_writes_partial_results(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rows.jsonl'
            def response(url, body):
                result = Mock(url=url, text=body, content=body.encode())
                return result
            session = Mock()
            session.headers = {}
            session.request.side_effect = [response(LANDING, SELECTOR), response(INVENTORY, TREE), response(URL, FIGURE)]
            with patch('municipio.adapters.fregenal_de_la_sierra.requests.Session') as factory:
                factory.return_value.__enter__.return_value = session
                result = FregenalDeLaSierraAyuntamientoAdapter('fregenal-de-la-sierra').backfill_proyectos(output)
            self.assertEqual(result['count'], 1)
            self.assertEqual(session.request.call_args_list[1].args, ('POST', INVENTORY))
            self.assertEqual(session.request.call_args_list[1].kwargs['data'], {'municipioseleccionado': '75'})
            self.assertEqual(json.loads(output.read_text())['id'], 'fregenal-sitex-40684')
            previous = output.read_bytes()
            session.request.side_effect = [response(LANDING, SELECTOR), response(INVENTORY, TREE), response(URL, '')]
            with patch('municipio.adapters.fregenal_de_la_sierra.requests.Session') as factory:
                factory.return_value.__enter__.return_value = session
                with self.assertRaises(ValueError):
                    FregenalDeLaSierraAyuntamientoAdapter('fregenal-de-la-sierra').backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
