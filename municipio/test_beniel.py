import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.beniel import (
    BenielAyuntamientoAdapter, INVENTORY, category_url, document_url,
    parse_instrument, parse_page,
)
from municipio.manifest import load_manifest


def page(folders=(), docs=()):
    source = 'Ayuntamiento de Beniel <table id="tablaDocumentosEnlaces"></table>\n'
    for identifier, title, count in folders:
        fragment = (f"<a onclick='pulsaEpigrafe({identifier})'><h4>{title} "
                    f"<span class='badge'>{count}</span></h4></a>")
        source += "html_epigrafes += " + json.dumps(fragment) + ";\n"
    for identifier, title in docs:
        fragment = f"<tr><td><a onclick='verDoc({identifier})'>{title}</a></td></tr>"
        source += 'jQuery("#tablaDocumentosEnlaces > tbody").append(' + json.dumps(fragment) + ');\n'
    return source


class BenielParserTests(unittest.TestCase):
    def test_group_documents_preserve_titles_and_no_inferred_dates(self):
        folders, _ = parse_page(page([(669, "7.1.1 MODIFICACIÓN PUNTUAL Nº 1 EL MOJÓN", 3)]))
        row = parse_instrument(folders[0], page(docs=[
            (303658, "Aprobación Definitiva"), (50364, "Documento Inicial Estratégico"),
            (203364, "Proyecto Modificación Puntual")]))
        self.assertEqual(row['id'], 'beniel-plan-669')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['url'], document_url('50364'))
        self.assertEqual(row['codigo_ine'], '30010')
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)

    def test_counts_and_document_isolation(self):
        folder = {'id': '670', 'titulo': 'ESTUDIO DE DETALLE REVISADO Nº 01/24', 'count': 2}
        row = parse_instrument(folder, page(docs=[(1, 'Memoria'), (2, 'Planos')]))
        self.assertEqual([d['id'] for d in row['documentos']], ['1', '2'])
        with self.assertRaises(ValueError):
            parse_instrument(folder, page(docs=[(1, 'Memoria')]))
        with self.assertRaises(ValueError):
            parse_instrument(folder, page(docs=[(1, 'Memoria'), (1, 'Duplicado')]))

    def test_fail_closed_on_changed_nested_inventory(self):
        with self.assertRaises(ValueError):
            parse_instrument({'id': '681', 'titulo': 'Plan General', 'count': 1},
                             page([(999, 'Subcarpeta', 1)]))

    def test_reject_form_procurement_and_news(self):
        for title in ('Solicitud licencia de obras', 'Anuncio de licitación', 'Fiestas patronales'):
            with self.assertRaises(ValueError):
                parse_instrument({'id': '1', 'titulo': title, 'count': 1}, page(docs=[(1, 'Documento')]))

    def test_missing_source_and_pagination(self):
        with self.assertRaises(ValueError):
            parse_page('<title>Captcha</title>')
        source = page([(1, 'Plan General', 1)])
        with self.assertRaises(ValueError):
            parse_page(source + 'html_epigrafes += "<a href=\'/page/2\'>Siguiente</a>";')
        # The global procedure search controls must not be mistaken for planning pagination.
        self.assertEqual(len(parse_page(source + '<input name="pagina" value="1">')[0]), 1)

    def test_unicode_escaped_html_literals(self):
        folders, _ = parse_page(page([(681, '7.1.3 Plan General Municipal de Ordenación', 1)]))
        self.assertEqual(folders[0]['titulo'], 'Plan General Municipal de Ordenación')

    def test_adapter_fetches_every_instrument_and_updates_full_snapshot(self):
        pages = {INVENTORY: page([(681, 'Plan General Municipal de Ordenación', 1),
                                  (670, 'ESTUDIO DE DETALLE REVISADO Nº 01/24', 1)]),
                 category_url('681'): page(docs=[(305006, 'Avance MEMORIA')]),
                 category_url('670'): page(docs=[(294138, 'Memoria Estudio Detalle')])}
        adapter = BenielAyuntamientoAdapter('beniel')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda s, u: pages[u]):
            output = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 2)
            self.assertEqual(len(output.read_text().splitlines()), 2)
            previous = output.read_text()
            pages[category_url('670')] = page()
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), previous)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('beniel')
        self.assertEqual((manifest.nombre, manifest.provincia), ('Beniel', 'Murcia'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.beniel:BenielAyuntamientoAdapter')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertTrue(BenielAyuntamientoAdapter('beniel').backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
