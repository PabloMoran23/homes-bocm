import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.arriate import (
    ArriateAyuntamientoAdapter, SOURCE, apply_ajax, more_button, official,
    parse_inventory, prepare,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

BASE = 'https://arriate.sedelectronica.es'
DOC = BASE + '/preview-document/'


def page(contents, more=''):
    return ('<table class="TransparencyListPanel"><tbody>' + contents + '</tbody></table>' + more)


def doc(identifier, title):
    return f'<tr id="row-{identifier}"><td><a href="{DOC}{identifier}">{title}</a></td></tr>'


def folder(title, count, target):
    return {'titulo': title, 'count': count, 'callback': BASE + '/transparency/' + target + '/'}


class ArriateTests(unittest.TestCase):
    def test_manifest_and_adapter_contract(self):
        manifest = load_manifest('arriate')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('29020', 'Arriate', 'Málaga'))
        for group, key in [('licencias', 'enabled'), ('schedule', 'enabled'),
                           ('geocode', 'jitter_missing')]:
            self.assertIs(raw[group][key], False)
        self.assertIsInstance(load_portal_adapter(manifest), ArriateAyuntamientoAdapter)

    def test_wicket_pagination_adds_documents_and_removes_button(self):
        button = '<div id="more"><button onclick="wicketAjaxGet(\'?x=next\')">Mostrar más</button></div>'
        soup = prepare(page(doc('a', 'DILIGENCIA aprobación'), button), SOURCE)
        self.assertIsNotNone(more_button(soup))
        xml = ('<?xml version="1.0"?><ajax-response>'
               '<component id="row-b" encoding="wicket1"><![CDATA[' +
               doc('b', 'COPIA AUTENTICA [Documento Innovación UE-6]^') +
               ']]></component><component id="more"><![CDATA['
               '<div id="more" style="display:none"></div>]]></component></ajax-response>')
        apply_ajax(soup, xml, BASE + '/?x=next')
        docs, folders = parse_inventory(soup)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[1]['titulo'], 'COPIA AUTENTICA [Documento Innovación UE-6]')
        self.assertFalse(folders)
        self.assertIsNone(more_button(soup))

    def test_missing_and_hostile_inventory_fail(self):
        with self.assertRaises(ValueError):
            parse_inventory(prepare('<html>Challenge</html>', SOURCE))
        with self.assertRaises(ValueError):
            parse_inventory(prepare(page('<a href="https://example.org/preview-document/a">Plan</a>'), SOURCE))
        with self.assertRaises(ValueError):
            official('https://example.org/transparency/')
        with self.assertRaises(ValueError):
            apply_ajax(prepare(page(''), SOURCE), '<ajax-response/>', SOURCE)

    def test_recursive_grouping_counts_and_no_inferred_dates(self):
        planning = folder('PLANEAMIENTO URBANÍSTICO', 3, 'planning')
        ue6 = folder('Innovación PGOU Arriate para ampliación suelo industrial: Creación UE-6', 2, 'ue6')
        pmvs = folder('PMVS 2019-2023 - Plan de Vivienda y Suelo', 2, 'pmvs')
        drawings = folder('PLANOS', 1, 'drawings')
        edar = folder('Proyecto construcción EDAR Y COLECTORES ARRIATE', 1, 'edar')
        ftth = folder('Plan Despliegue Red Fibra Optica FTTH', 13, 'ftth')
        adapter = ArriateAyuntamientoAdapter('arriate')
        inventory = {
            SOURCE: (SOURCE, [], [planning, pmvs, edar, ftth]),
            planning['callback']: (planning['callback'], [{'titulo': 'BOP sin vinculación verificada', 'url': DOC+'loose'}], [ue6]),
            ue6['callback']: (ue6['callback'], [{'titulo': 'Diligencia', 'url': DOC+'ue-a'}, {'titulo': 'Innovación', 'url': DOC+'ue-b'}], []),
            pmvs['callback']: (pmvs['callback'], [{'titulo': 'TOMO I Abril19', 'url': DOC+'pmvs'}], [drawings]),
            drawings['callback']: (drawings['callback'], [{'titulo': 'Plano', 'url': DOC+'map'}], []),
            edar['callback']: (edar['callback'], [{'titulo': 'Tomo 1', 'url': DOC+'edar'}], []),
        }
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_inventory', side_effect=lambda session, url: inventory[url]):
                result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['count'], 3)
            self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1])
            self.assertEqual(rows[1]['documentos'][1]['inventory_url'], drawings['callback'])
            self.assertNotIn(DOC+'loose', json.dumps(rows))
            for row in rows:
                self.assertFalse(row['publication_ready'])
                for key in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                    self.assertNotIn(key, row)
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')

    def test_truncated_inventory_rejected(self):
        adapter = ArriateAyuntamientoAdapter('arriate')
        f = folder('UE-6', 16, 'ue6')
        with patch.object(adapter, '_inventory', return_value=(f['callback'], [{'url': DOC+'a'}]*10, [])):
            with self.assertRaisesRegex(ValueError, 'Incomplete folder'):
                adapter._collect(None, f, set())

    def test_pagination_loop_rejected(self):
        class Response:
            url = SOURCE
            text = page(doc('a', 'Innovación'), '<button onclick="wicketAjaxGet(\'?x=repeat\')">Mostrar más</button>')
        adapter = ArriateAyuntamientoAdapter('arriate')
        with patch.object(adapter, '_fetch', return_value=Response()):
            with self.assertRaisesRegex(ValueError, 'Repeated pagination'):
                adapter._inventory(None, SOURCE)


if __name__ == '__main__':
    unittest.main()
