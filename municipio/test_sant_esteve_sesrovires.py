import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_esteve_sesrovires import (
    SOURCES, SantEsteveSesroviresAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def section(title, docs, anchor='marcador0'):
    links = ''.join(f'<a href="https://www.seu.cat/seue-fitxer?id={n}">{label}</a>' for n, label in docs)
    return f'<div class="subtitle" id="{anchor}">{title}</div><br><div class="ddbbtext">{links}</div>'


def page(body):
    return '<main id="main-content"><div class="dinamic">' + body + '</div><p>Darrera actualització: 17.03.2016</p></main>'


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.urban = section("Resolució d'al·legacions i aprovació definitiva del Projecte d'Urbanització Polígon Industrial Sesrovires", [(1, 'Certificat acord'), (2, 'Volum 1'), (3, 'Volum 2')])
        self.reparcel = section("Aprovació definitiva del Projecte de Reparcel·lació del Polígon Industrial Sesrovires", [(4, 'Memòria'), (5, 'Plànols')], 'marcador1')

    def test_group_documents_and_preserve_distinct_instruments(self):
        rows = Adapter.parse_inventory(page(self.urban + self.reparcel), SOURCES[0])
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[1]['tipo'], 'reparcelacion')
        self.assertEqual(rows[0]['fase'], 'aprobación definitiva')
        self.assertEqual(rows[0]['documentos'][0]['source_url'], SOURCES[0])
        for row in rows:
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[field])
        reordered = Adapter.parse_inventory(page(self.reparcel + self.urban), SOURCES[0])
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in reordered})

    def test_auxiliary_form_is_retained_but_not_a_record(self):
        body = section('Projecte complementari urbanització millora accessos B-224', [(7, 'Projecte'), (8, 'Model al·legacions')])
        rows = Adapter.parse_inventory(page(body), SOURCES[2])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['fase'])
        self.assertEqual(rows[0]['documentos'][1]['rol'], 'formulario_auxiliar')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(page(section('Projecte urbanització', [(8, 'Model al·legacions')])), SOURCES[2])

    def test_general_plan_initial_stage(self):
        row = Adapter.parse_inventory(page(section('Aprovació inicial modificació puntual PGOM àmbit SUP 05- Industrial SEAT', [(9, 'Memòria')])), SOURCES[1])[0]
        self.assertEqual(row['tipo'], 'modificacion_planeamiento')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(row['codigo_ine'], '08208')

    def test_reject_pagination_and_changed_markup(self):
        for html in [page(''), '<h1>Login</h1>', page(self.urban + '<nav class="pagination">2</nav>'),
                     page(self.urban + '<a href="?page=2">2</a>'),
                     page(self.urban + '<a href="/next" rel="next">more</a>'),
                     page(self.urban + '<div class="ddbbtext">orphan</div>'),
                     page(section('Llicència obres formulari', [(10, 'Sol·licitud')])),
                     page(section('Anunci de licitació Projecte urbanització', [(10, 'Plec')])),
                     page(self.urban.replace('https://www.seu.cat/seue-fitxer?id=1', 'https://example.org/file.pdf')),
                     page('<div class="subtitle">Projecte urbanització sense documents</div>' + self.urban)]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html, SOURCES[0])

    def test_live_fetch_contract_and_atomic_failure(self):
        class Response:
            headers = {'Content-Type': 'text/html; charset=utf-8'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield page(body).encode()
        body = self.urban
        adapter = Adapter('sant-esteve-sesrovires')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'records.jsonl'
            out.write_text('previous complete snapshot')
            # Same instrument repeated on multiple sources must not silently duplicate.
            with patch('municipio.adapters.sant_esteve_sesrovires.requests.get', return_value=Response()), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous complete snapshot')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('sant-esteve-sesrovires')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)


if __name__ == '__main__':
    unittest.main()
