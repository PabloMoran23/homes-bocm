"""Self-contained parser tests; live evidence is deliberately not a fixture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.firgas import FirgasAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest


def panel(title, content):
    return f'<div class="wgl-accordion_panel"><h4 class="wgl-accordion_header">{title}</h4>{content}</div>'


def table(headers, values):
    return '<table><tr>' + ''.join(f'<th>{v}</th>' for v in headers) + '</tr><tr>' + ''.join(f'<td>{v}</td>' for v in values) + '</tr></table>'


def fixture():
    approval = ('Aprobación Definitiva Parcial Aprobado el 08/06/1999 '
                '<a href="/boc1999">Publicado en el BOC del día 06/10/1999 Nº 134</a> '
                'Aprobación Definitiva Aprobado el 09/04/2001 '
                '<a href="/boc2001">Publicado en el BOC del día 12/11/2001 Nº 147</a> '
                '<a href="/bop2001">Publicado en el BOP del día 14/12/2001 Nº 150</a>')
    amendments = table(['Fase', 'Revisión', 'A. COTMAC', 'Acuerdo Plenario', 'Fecha BOC', 'Nº BOC', 'Fecha BOP', 'Nº BOP'],
                       ['Avance', 'Avance. Revisión Parcial Parque Industrial Las Huertecillas.', '', '14/02/2011', '', '', '13/05/2011', '<a href="/revision.pdf">63</a>'])
    partials = table(['Nombre', 'Fase', 'Fecha de aprobación', 'Fecha BOC', 'Nº BOC', 'Fecha BOP', 'Nº BOP'],
                     ['Plan Parcial SAU 3 Mesetas de Casablanca', 'Aprobación Definitiva', '10/08/2005', '27/09/2005', '<a href="/pp-boc">190</a>', '31/08/2005', '<a href="/pp-bop">111</a>'])
    return ('<h2>NNSS (Normas Subsidiarias).</h2>' +
            panel('2. Aprobación y Publicación', approval) +
            panel('3. Modificaciones / Revisiones', amendments) +
            panel('4. Archivos del Planeamiento', '<a href="/memoria.pdf">Memoria</a><a href="/normativa.pdf">Normativa</a><a href="/plano.pdf">Plano</a>') +
            panel('6. Planes Parciales', partials) +
            '<h2>PGO (Plan General de Ordenación).</h2>' +
            panel('2. Aprobación y Publicación', '<a href="/pgo.pdf">PGO caducado</a>') +
            '<a href="/licitacion">Licitación obras</a><a href="/formulario">Solicitud licencia</a>')


class FirgasTests(unittest.TestCase):
    def test_groups_documents_and_isolates_instruments(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]['documentos']), 6)
        self.assertEqual([d['url'] for d in rows[1]['documentos']], [SOURCE.replace('/urbanismo/', '/revision.pdf')])
        self.assertNotIn('pgo.pdf', json.dumps(rows))
        self.assertNotIn('licitacion', json.dumps(rows))
        self.assertNotIn('formulario', json.dumps(rows))
        self.assertTrue(all(r['codigo_ine'] == '35008' and r['lat'] is None and not r['publication_ready'] for r in rows))

    def test_dates_keep_semantics_and_all_publications(self):
        nnss, amendment, partial = parse_inventory(fixture())
        self.assertEqual(nnss['eventos'][0]['fecha_aprob'], '1999-06-08')
        self.assertEqual(nnss['eventos'][1]['fecha_aprob'], '2001-04-09')
        self.assertEqual([p['fecha_publicacion'] for p in nnss['eventos'][1]['publicaciones']], ['2001-11-12', '2001-12-14'])
        self.assertEqual(amendment['fecha_acuerdo'], '2011-02-14')
        self.assertNotIn('fecha_aprob', amendment)
        self.assertEqual(partial['fecha_aprob'], '2005-08-10')
        self.assertEqual([p['fecha_publicacion'] for p in partial['publicaciones']], ['2005-09-27', '2005-08-31'])

    def test_fails_closed_on_changed_or_incomplete_sources(self):
        for html in ('<a href="/plan.pdf">Plan Parcial</a>',
                     fixture().replace('Planes Parciales', 'Planes'),
                     fixture().replace('10/08/2005', '32/08/2005'),
                     fixture().replace('Fecha de aprobación', 'Fecha desconocida')):
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_unlinked_bulletin_keeps_inventory_provenance(self):
        html = fixture().replace('<a href="/pp-boc">190</a>', '190')
        publication = parse_inventory(html)[2]['publicaciones'][0]
        self.assertIsNone(publication['url'])
        self.assertEqual(publication['numero'], '190')
        self.assertEqual(publication['source_url'], SOURCE)

    def test_rejects_pagination(self):
        html = fixture().replace('Memoria</a>', 'Memoria</a><a rel="next" href="?page=2">Next</a>')
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(html)

    def test_live_fetch_contract_and_full_snapshot_update(self):
        response = Mock(url=SOURCE, text=fixture())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.firgas.requests.get', return_value=response) as get:
            adapter = FirgasAyuntamientoAdapter('firgas')
            target = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(target, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(target.read_text().splitlines()), 3)
            get.assert_called_once()
            response.raise_for_status.assert_called_once()

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('firgas')
        self.assertEqual(manifest.provincia, 'Las Palmas')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'licencias.jsonl'
            result = FirgasAyuntamientoAdapter('firgas').backfill_licencias(target)
            self.assertTrue(result['disabled'])
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
