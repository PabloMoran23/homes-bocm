"""Offline tests for the SITU@ protocol and municipal document semantics."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.almogia import (
    AlmogiaAyuntamientoAdapter, INVENTORY, parse_documents, parse_inventory_page,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(identifier='399', total=1):
    return {'iTotalDisplayRecords': total, 'iTotalRecords': total, 'aaData': [[
        'MÁLAGA', 'ALMOGÍA', 'NNSS', '23/04/97', 'Pre LOUA', '',
        f"<a class='docuPlan' name={identifier} href='#'>Documentos</a>", '',
    ]]}


def detail(identifier='399'):
    entries = [
        {'nombre': 'Normas urbanísticas', 'enlace': '<a href="descargaDocumentos.jsf?doc=63734">PDF</a>', 'clave': '6768-Normas'},
        {'nombre': 'Normas urbanísticas', 'enlace': '<a href="descargaDocumentos.jsf?doc=63734">PDF</a>', 'clave': '6768DocumentosTécnicos'},
        {'nombre': 'Normas urbanísticas', 'enlace': '<a href="descargaDocumentos.jsf?doc=75786">PDF</a>', 'clave': '6767-Normas'},
    ]
    values = [('Figura', 'NNSS - Normas Subsidiarias Municipales'), ('Objeto', '1997'),
              ('Ámbito Territorial', 'MUNICIPAL - Municipal ALMOGÍA'),
              ('Estado', 'Vigente'), ('Fecha de Aprobación', '23/04/97')]
    cells = ''.join(f'<tr><td><span class="area-filter-label">{k}:</span></td><td>{v}</td></tr>' for k, v in values)
    return (f'<form action="result.jsf"><input type="hidden" name="codFigura" value="{identifier}">'
            f'<table class="area-filters">{cells}</table>'
            '<a onclick="jsfcljs(f,{\'share\':\'share\'},\'\')"><img title="Compartir url"></a></form>'
            '<script>var mapa=' + json.dumps(entries) + ';</script>')


class Response:
    def __init__(self, html='', payload=None):
        self.text = html
        self.payload = payload
        self.url = INVENTORY

    def json(self):
        return self.payload


class AlmogiaTests(unittest.TestCase):
    def test_manifest_and_adapter(self):
        manifest = load_manifest('almogia')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Almogía', 'Málaga', '29011'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), AlmogiaAyuntamientoAdapter)

    def test_group_documents_and_keep_source_semantics(self):
        rows, total = parse_inventory_page(inventory())
        row = parse_documents(detail(), rows[0])
        self.assertEqual(total, 1)
        self.assertEqual(row['fecha_aprob'], '1997-04-23')
        self.assertEqual(row['situadifusion_id'], '399')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['clasificaciones_fuente']), 2)
        self.assertNotEqual(row['documentos'][0]['url'], row['documentos'][1]['url'])
        for key in ('fecha', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase'):
            self.assertNotIn(key, row)

    def test_reject_unverified_or_changed_content(self):
        instrument = parse_inventory_page(inventory())[0][0]
        for html in ('<h1>Solicitud de licencia</h1>', detail('400'),
                     detail().replace('ALMOGÍA', 'MÁLAGA'),
                     detail().replace('23/04/97', '24/04/97'),
                     detail().replace('var mapa=', 'var removed='),
                     detail().replace('descargaDocumentos.jsf', 'other.jsf')):
            with self.subTest(html=html[:80]), self.assertRaises((ValueError, KeyError)):
                parse_documents(html, instrument)
        for payload in (inventory(total=0),
                        {**inventory(), 'aaData': [['Wrong schema']]},
                        {**inventory(), 'iTotalRecords': 4}):
            with self.assertRaises(ValueError):
                parse_inventory_page(payload)

    def run_snapshot(self, pages):
        adapter = AlmogiaAyuntamientoAdapter('almogia')
        listing = '<a id="form:tipoPlaneamiento" onclick="jsfcljs(f,{\'docs\':\'docs\'},\'\')"></a>'
        initial = '<a id="form:commandRedirige" onclick="jsfcljs(f,{\'search\':\'search\'},\'\')"></a>'
        offsets = []

        def fetch(session, method, url, **kwargs):
            if method == 'GET':
                return Response(initial)
            offsets.append(kwargs['data']['iDisplayStart'])
            return Response(payload=next(pages))

        def submit(session, response, fields):
            if 'search' in fields:
                return Response(listing)
            if 'docs' in fields:
                return Response(detail(fields['codFigura']))
            return Response('<input name="urlACompartir" value="https://ws132.juntadeandalucia.es/situadifusion/pages/documentosCompartir.jsf?fixture">')

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous successful snapshot')
            with patch.object(adapter, '_fetch', side_effect=fetch), patch.object(adapter, '_submit', side_effect=submit):
                try:
                    result = adapter.backfill_proyectos(output)
                except ValueError:
                    self.assertEqual(output.read_text(), 'previous successful snapshot')
                    raise
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        return result, rows, offsets

    def test_follow_pagination_and_separate_instruments(self):
        result, rows, offsets = self.run_snapshot(iter([inventory(total=2), inventory('400', total=2)]))
        self.assertEqual(offsets, ['0', '1'])
        self.assertEqual(result['live_records'], 2)
        self.assertEqual([r['id'] for r in rows], ['almogia-situa-399', 'almogia-situa-400'])

    def test_pagination_failures_preserve_previous_snapshot(self):
        empty = {**inventory(total=2), 'aaData': []}
        for pages in ([inventory(total=2), empty],
                      [inventory(total=2), inventory(total=2)],
                      [inventory(total=2), inventory('400', total=3)]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                self.run_snapshot(iter(pages))


if __name__ == '__main__':
    unittest.main()
