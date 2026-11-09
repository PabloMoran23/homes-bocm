"""Offline parser and pagination regressions; no evidence directory required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pulianas import (
    ROOT, PulianasAyuntamientoAdapter, inventory_url, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(entries, page=1, total=1):
    headers = ['Órgano Tramitador', 'Actuación', 'Provincia', 'Otras Provincias',
               'Municipio', 'Otros Municipios', 'Tipo de Resolución',
               'Fecha de Resolución', 'Número de Expediente', 'Resoluciones y Otros Documentos (*)']
    rows = ''
    for number, expediente in entries:
        values = ['Junta', 'PLAN PARCIAL PPR-05', 'GRANADA', '', 'PULIANAS', '',
                  'Admisión/ Inadmisión Trámite', '03/06/2020', expediente,
                  f'<a href="/medioambiente/daepu/resolucions/{number};jsessionid=ephemeral">Detalle</a>']
        rows += '<tr>' + ''.join(f'<td>{x}</td>' for x in values) + '</tr>'
    return '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>' + rows + f'<tr class="footer"><td>Página {page} de {total}</td></tr></table>'


def detail(expediente='EAE/2160/2020', number='one'):
    values = {'Órgano Tramitador:': 'Junta de Andalucía', 'Actuación:': 'PLAN PARCIAL PPR-05 DEL PLANEAMIENTO GENERAL DE PULIANAS',
              'Provincia:': 'GRANADA', 'Municipio:': 'PULIANAS', 'Número de Expediente:': expediente,
              'Fecha de Resolución:': '03/06/2020'}
    fields = ''.join(f'<div><label>{k}</label><div class="box">{v}</div></div>' for k, v in values.items())
    docs = [('Admisión/ Inadmisión Trámite', '03/06/2020', number),
            ('Publicación en BOJA (PB)', '22/12/2020', number + '-boja')]
    return fields + '<table><tr><th>Tipo</th><th>Fecha de Resolución</th><th>Enlace al documento</th></tr>' + ''.join(
        f'<tr><td>{kind}</td><td>{day}</td><td><a href="downloadFile/{doc}">Documento</a></td></tr>' for kind, day, doc in docs) + '</table>'


class PulianasTests(unittest.TestCase):
    def test_inventory_identity_canonical_links_and_pagination(self):
        rows, total = parse_inventory(inventory([('20200', 'EAE/2160/2020')], 2, 3), 2)
        self.assertEqual(total, 3)
        self.assertEqual(rows, [{'url': ROOT + 'resolucions/20200', 'expediente': 'EAE/2160/2020'}])
        for bad in [inventory([('20200', 'E')]).replace('PULIANAS', 'OTRO'),
                    inventory([('20200', 'E')]).replace('GRANADA', 'SEVILLA'),
                    inventory([('20200', 'E')]).replace('Página 1 de 1', ''),
                    '<html>Solicitud de licencia de obras</html>', inventory([])]:
            with self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_documents_grouped_and_dates_not_promoted_to_approval(self):
        row = parse_detail(detail(), ROOT + 'resolucions/20200', 'EAE/2160/2020')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '18165')
        self.assertEqual(row['documentos'][0]['fecha_resolucion_fuente'], '2020-06-03')
        self.assertIsNone(row['documentos'][1]['fecha_publicacion'])
        self.assertEqual(row['documentos'][1]['fecha_resolucion_fuente'], '2020-12-22')
        self.assertIsNone(row['documentos'][0]['fecha_publicacion'])
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['documentos'][0]['url'], ROOT + 'resolucions/downloadFile/one')

    def test_reject_missing_documents_forms_and_mismatched_detail(self):
        html = detail()
        for bad in [html.replace('PULIANAS', 'PELIGROS'),
                    html.replace('EAE/2160/2020', 'EAE/9999/2020'),
                    html.replace('PLAN PARCIAL', 'SOLICITUD DE LICENCIA'),
                    html.replace('downloadFile/', 'https://example.org/'),
                    html.split('<table>')[0], html.replace('03/06/2020', '31/02/2020')]:
            with self.assertRaises(ValueError):
                parse_detail(bad, ROOT + 'resolucions/20200', 'EAE/2160/2020')

    def test_live_path_walks_all_pages_and_merges_case_documents(self):
        pages = {
            inventory_url(1): inventory([('1', 'EAE/2160/2020')], 1, 2),
            inventory_url(2): inventory([('2', 'EAE/2160/2020'), ('3', 'EAE/2181/2020')], 2, 2),
            ROOT + 'resolucions/1': detail(number='one'),
            ROOT + 'resolucions/2': detail(number='two'),
            ROOT + 'resolucions/3': detail('EAE/2181/2020', 'three'),
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'projects.jsonl'
            adapter = PulianasAyuntamientoAdapter()
            with patch.object(adapter, '_fetch', side_effect=lambda session, url, capture: pages[url]) as fetch:
                report = adapter.backfill_proyectos(output)
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(report['rows'], 2)
            self.assertEqual(fetch.call_count, 5)
            self.assertEqual(len(records[0]['documentos']), 4)
            self.assertEqual(len(records[1]['documentos']), 2)
            self.assertEqual(len(records[0]['source_urls']), 2)
            # If a later page fails, a previous complete snapshot survives.
            before = output.read_text()
            pages[inventory_url(2)] = inventory([('1', 'EAE/2160/2020')], 2, 2)
            with patch.object(adapter, '_fetch', side_effect=lambda session, url, capture: pages[url]):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), before)
            adapter.backfill_licencias(Path(tmp) / 'licences.jsonl')
            self.assertEqual((Path(tmp) / 'licences.jsonl').read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('pulianas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Pulianas', 'Granada', '18165'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.pulianas:PulianasAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
