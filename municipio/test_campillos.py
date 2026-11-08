import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.campillos import (
    CampillosAyuntamientoAdapter, SOURCE, ajax_components, group_projects,
    next_action, parse_rows,
)
from municipio.manifest import load_manifest


def row(name, identifier, expediente='3169/2025', category='Urbanismo'):
    values = {'name': f'<a href="/preview-document/{identifier}">{name}</a>',
              'folderCode': expediente, 'folderName': 'Licencias Urbanísticas',
              'boardCategory': category, 'description': 'IP proyecto actuación', 'dateFrom': '27/10/2026'}
    return '<tr>' + ''.join(f'<td class="class_{k}">{v}</td>' for k, v in values.items()) + '</tr>'


class CampillosTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        html = '<table>' + row('PROYECTO ACTUACION EXTRAORDINARIA DEFINITIVA', 'project')
        html += row('ANUNCIO DE INFORMACIÓN PÚBLICA', 'notice')
        html += row('Solicitud licencia de obras', 'form', '1/2026')
        html += row('PROYECTO ACTUACION', 'unrelated', '2/2026', 'Empleo Público') + '</table>'
        rows = parse_rows(html)
        projects = group_projects(rows + rows)
        self.assertEqual(len(projects), 1)
        p = projects[0]
        self.assertEqual(len(p['documentos']), 2)
        self.assertEqual(p['fecha_publicacion'], '2026-10-27')
        self.assertIsNone(p['fecha_aprob'])
        self.assertIsNone(p['fecha_acuerdo'])
        self.assertNotIn('fase', p)  # DEFINITIVA in filename is not approval.
        self.assertNotIn('lat', p)
        with self.assertRaises(ValueError):
            group_projects(parse_rows('<table>' + row('Solicitud de licencia', 'form') + '</table>'))

    def test_pagination_parser(self):
        more = '<div class="more_results"><button onclick="wicketAjaxGet(\'?x=next\',null)">Mostrar más</button></div>'
        self.assertEqual(next_action(more), '?x=next')
        xml = '<ajax-response><component id="rows"><![CDATA[<table>' + row('ANUNCIO', 'notice') + '</table>]]></component><component id="more"><![CDATA[<div style="display:none"></div>]]></component></ajax-response>'
        fragment = ajax_components(xml)
        self.assertEqual(len(parse_rows(fragment)), 1)
        self.assertIsNone(next_action(fragment))
        for invalid in ['<button>Mostrar más</button>', '<a href="?page=2">Siguiente</a>']:
            with self.assertRaises(ValueError):
                next_action(invalid)
        with self.assertRaises(ValueError):
            ajax_components('<ajax-response><redirect>login</redirect></ajax-response>')

    def test_live_flow_follows_ajax_and_groups_later_documents(self):
        first = '<table>' + row('PROYECTO ACTUACION EXTRAORDINARIA', 'project') + '</table><div class="more_results"><button onclick="wicketAjaxGet(\'?x=next\',null)">Mostrar más</button></div>'
        second = '<ajax-response><component id="rows"><![CDATA[<table>' + row('ANUNCIO', 'notice') + '</table>]]></component><component id="more"><![CDATA[<div style="display:none"></div>]]></component></ajax-response>'
        class Response:
            def __init__(self, text): self.text = text
        adapter = CampillosAyuntamientoAdapter('campillos')
        notice = 'En el Ayuntamiento de Campillos se admite la solicitud [Expte. 3169/2025] El proyecto de actuación se somete a información pública'
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_get', side_effect=[Response(first), Response(second)]) as fetch, patch.object(adapter, '_document_text', side_effect=['PROYECTO PARA ACTUACIÓN EXTRAORDINARIA NAVE PROMOTOR: alguien', notice]):
            result = adapter.backfill_proyectos(Path(tmp) / 'projects.jsonl')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['pages'], 2)
            self.assertEqual(fetch.call_args.args[1], SOURCE + '?x=next')
            self.assertIn('información pública', (Path(tmp) / 'projects.jsonl').read_text())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('campillos')
        self.assertEqual(manifest.provincia, 'Málaga')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(CampillosAyuntamientoAdapter('campillos').backfill_licencias(p)['rows'], 0)
            self.assertEqual(p.read_text(), '')


if __name__ == '__main__':
    unittest.main()
