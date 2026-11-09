"""Offline parser and pagination regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from municipio.adapters.adamuz import AdamuzAyuntamientoAdapter, parse_page, parse_documents
from municipio.manifest import load_manifest, load_yaml


def page(ids, total=None):
    return {'iTotalRecords': total if total is not None else len(ids),
            'iTotalDisplayRecords': total if total is not None else len(ids),
            'aaData': [['CÓRDOBA', 'ADAMUZ', 'PAP', '09/05/19', 'LOUA', '',
                        f'<a class="docuPlan" name="{i}"></a>', ''] for i in ids]}


ITEM = parse_page(page(['86900']))[1][0]


def document_html(code='86900', muni='14001', docs=None):
    if docs is None:
        docs = [{'nombre': 'Memoria', 'enlace': '<a class="descargaDoc" href="descargaDocumentos.jsf?doc=1"></a>', 'clave': 'hito'},
                {'nombre': 'Memoria', 'enlace': '<a class="descargaDoc" href="descargaDocumentos.jsf?doc=1"></a>', 'clave': 'hito-Memoria'},
                {'nombre': 'Normas', 'enlace': '<a class="descargaDoc" href="descargaDocumentos.jsf?doc=2"></a>', 'clave': 'hito'}]
    fields = {'Figura': 'PAP - Procedimiento de Adaptación Parcial', 'Objeto': 'Adaptación Parcial a la LOUA',
              'Ámbito Territorial': 'MUNICIPAL - Municipal ADAMUZ', 'Estado': 'Vigente', 'Fecha de Aprobación': '09/05/19'}
    return (f'<input name="codFigura" value="{code}"><input name="codigosMunicipios" value="{muni}">'
            '<table class="area-filters">' + ''.join(
                f'<tr><td><span class="area-filter-label">{k}:</span></td><td>{v}</td></tr>' for k, v in fields.items()) +
            '</table><script>var mapa=' + json.dumps(docs) + ';</script>' +
            '<table id="j_id6:tablaExporResult_table"><tbody><tr><td>Memoria</td></tr><tr><td>Normas</td></tr></tbody></table>')


class AdamuzParserTests(unittest.TestCase):
    def test_group_documents_and_explicit_dates(self):
        row = parse_documents(document_html(), ITEM)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['grupos_fuente'], ['hito', 'hito-Memoria'])
        self.assertEqual(row['fecha_aprob'], '2019-05-09')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertNotIn('fecha', row)
        self.assertNotIn('lat', row)
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '14001')

    def test_reject_forms_news_and_missing_documents(self):
        for html in ['<a>Solicitud licencia de obras</a>', '<h1>Noticias de Adamuz</h1>', document_html(docs=[])]:
            with self.assertRaises(ValueError):
                parse_documents(html, ITEM)

    def test_instrument_and_municipality_isolation(self):
        for html in [document_html(code='3866'), document_html(muni='46001')]:
            with self.assertRaises(ValueError):
                parse_documents(html, ITEM)
        wrong = page(['1']);wrong['aaData'][0][1] = 'ADEMUZ'
        with self.assertRaises(ValueError):
            parse_page(wrong)

    def test_reject_incomplete_document_export(self):
        with self.assertRaises(ValueError):
            parse_documents(document_html().replace('<tr><td>Normas</td></tr>', ''), ITEM)

    def test_all_server_pages_are_consumed(self):
        adapter = AdamuzAyuntamientoAdapter('adamuz')
        response = SimpleNamespace(text='<form><a id="j_id6:tipoPlaneamiento"></a></form>', url='https://ws132.juntadeandalucia.es/situadifusion/pages/result.jsf')
        pages = [SimpleNamespace(json=lambda: page(['1'], 2)), SimpleNamespace(json=lambda: page(['2'], 2))]
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_search', return_value=response), \
                patch.object(adapter, '_request', side_effect=pages) as request, \
                patch.object(adapter, '_submit', return_value=SimpleNamespace(text='detail')), \
                patch('municipio.adapters.adamuz.parse_documents', side_effect=lambda html, item: {'id': item['situa_id']}):
            path = Path(folder) / 'records.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['count'], 2)
            self.assertEqual([c.kwargs['data']['iDisplayStart'] for c in request.call_args_list], [0, 1])
            self.assertEqual([json.loads(x)['id'] for x in path.read_text().splitlines()], ['1', '2'])

    def test_pagination_anomalies_fail_without_replacing_output(self):
        for second in [page([], 2), page(['1'], 2), page(['2'], 3)]:
            adapter = AdamuzAyuntamientoAdapter('adamuz')
            pages = [SimpleNamespace(json=lambda: page(['1'], 2)), SimpleNamespace(json=lambda: second)]
            with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_search'), patch.object(adapter, '_request', side_effect=pages):
                path = Path(folder) / 'records.jsonl';path.write_text('previous snapshot')
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
                self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('adamuz');raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('14001', 'Adamuz', 'Córdoba'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'licencias.jsonl'
            self.assertTrue(AdamuzAyuntamientoAdapter('adamuz').backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
