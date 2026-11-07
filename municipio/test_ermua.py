import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ermua import ErmuaAyuntamientoAdapter, SOURCE, parse_inventory, parse_plan
from municipio.manifest import load_manifest


def page(body, title='Plan general de ordenación urbana'):
    return f'<h1>{title}</h1><article class="node"><div class="field--name-body">{body}</div></article>'


def doc(name):
    return f'<a href="/sites/default/files/{name}.pdf">{name}</a>'


PGOU = page('<p>El plan general de ordenación urbana de Ermua aprobado en el año 2015.</p>'
            + doc('base') + doc('base')
            + '<ul><li>2018: Aprobación definitiva de la 1ª Modificación Puntual del PGOU URETA</li></ul>'
            + doc('ureta')
            + '<p><a href="/es/sesiones_organos_gobierno/ple12018">Sesión de pleno</a></p>'
            + '<ul><li>2025: Aprobación Definitiva de la 3ª Modificación Puntual del PGOU IDESA</li></ul>'
            + doc('idesa'))
INVENTORY = page('<h2>Urbanismo</h2>' + ''.join(
    f'<a href="{SOURCE}/{slug}">{title}</a>' for slug, title in [
        ('pgou', 'Plan General de Ordenación Urbana'),
        ('casco', 'Plan Especial del Casco Histórico'),
        ('senda', 'Plan Especial de Senda Verde')])
    + '<a href="/formulario">Solicitud de licencia</a><h2>Deportes</h2>'
    + '<a href="/otro">Plan Especial de deportes</a>', 'Planes municipales')


class ErmuaTests(unittest.TestCase):
    def test_grouping_dates_provenance_and_stability(self):
        rows = parse_plan(PGOU, SOURCE + '/pgou')
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 1])
        self.assertEqual([r['anio_aprobacion'] for r in rows], [2015, 2018, 2025])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        self.assertEqual(rows[1]['parent_id'], rows[0]['id'])
        for r in rows:
            self.assertIsNone(r['fecha_publicacion'])
            self.assertIsNone(r['fecha_acuerdo'])
            self.assertIsNone(r['fecha_aprob'])
            self.assertIsNone(r['geometry'])
            self.assertEqual(r['documentos'][0]['source_url'], SOURCE + '/pgou')
        self.assertEqual(rows, parse_plan(PGOU, SOURCE + '/pgou'))

    def test_inventory_scope_and_fail_closed(self):
        self.assertEqual(len(parse_inventory(INVENTORY)), 3)
        for html in ['', '<h1>Solicitud de licencia</h1>', page('<p>Sin documentos</p>')]:
            with self.assertRaises(ValueError):
                parse_plan(html, SOURCE)
        for extra in ['<a rel="next" href="?page=1">2</a>', '<nav class="pager"><a href="?page=1">2</a></nav>', '<a href="?page=1">Siguiente</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(INVENTORY + extra)
        with self.assertRaises(ValueError):
            parse_inventory(page('<h2>Urbanismo</h2>'))
        with self.assertRaises(ValueError):
            parse_plan(PGOU.replace('1ª Modificación', 'Primera Modificación'), SOURCE)

    def test_special_plan_is_not_an_approval(self):
        row, = parse_plan(page('<p>Este plan pretende crear una senda.</p>' + doc('memoria'), 'Plan Especial Senda Verde'), SOURCE + '/senda')
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['anio_aprobacion'])
        self.assertIn('pretende', row['descripcion'])

    def test_adapter_and_manifest(self):
        manifest = load_manifest('ermua')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        self.assertFalse(manifest.licencias.enabled)
        adapter = ErmuaAyuntamientoAdapter('ermua')
        special = page(doc('memoria'), 'Plan Especial Casco')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[INVENTORY, PGOU, special, special]):
            path = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 5)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 5)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
