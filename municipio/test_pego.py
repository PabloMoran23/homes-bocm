"""Offline parser and adapter-contract checks; no live network needed."""
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.pego import PegoAyuntamientoAdapter, SOURCE, publication_date
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def item(title, content):
    return f'<details><summary>{title}</summary>{content}</details>'


def link(label, url='/wp-content/uploads/2025/11/a.pdf'):
    return f'<a href="{url}">{label}</a>'


def inventory():
    lightbox = '#elementor-action%3Aaction%3Dlightbox%26settings%3D' + base64.b64encode(
        json.dumps({'url': 'https://pego.servidortigres.com/plan.jpg'}).encode()).decode()
    return '<h2>Pla General Ordenació Urbana</h2><div class="e-n-accordion">' + ''.join([
        item('Revisió del Pla General Ordenació Urbana de Pego',
             link('BOP 135 1999-06-15') + link('BOP 135 1999-06-15') +
             link('BOP 50 1999-03-02', '/b.pdf') + link('Plànol', lightbox)),
        item("Pla parcial modificatiu d'alineacions del sector Calvari I",
             link('DOGV 3924 24.01.2001', '/calvari.pdf')),
        item('Modificacions puntuals', '<h3>MP 01: Mont Pego</h3>' + link('MEMÒRIA', '/mp1.pdf') +
             '<h3>MP 02: carrer Vallet</h3>' + link('DOGV 4405 24.12.2002', '/mp2.pdf')),
        item('Plans Especials', '<h3>Pla Especial Num. 1: piscina coberta</h3>' + link('MEMÒRIA', '/pe1.pdf')),
        item('Normativa', link('Solicitud licencia')),
        item("Béns d'interès cultural", link('Castell d’Oliva')),
    ]) + '</div><h3>Información pública de licencia ambiental</h3>' + link('Edicte')


class PegoTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = PegoAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['fechas_publicacion_documentos'], ['1999-03-02', '1999-06-15'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertEqual(rows[1]['fecha_publicacion'], '2001-01-24')
        self.assertEqual(rows[2]['documentos'][0]['url'], 'https://pego.org/mp1.pdf')
        self.assertEqual(rows[3]['documentos'][0]['url'], 'https://pego.org/mp2.pdf')
        self.assertEqual(rows[0]['documentos'][2]['url'], 'https://pego.servidortigres.com/plan.jpg')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '03102')
            for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
        self.assertIsNone(publication_date('MEMÒRIA 12.01.2025'))
        self.assertIsNone(rows[2]['fecha_publicacion'])

    def test_fail_closed(self):
        for html in ('<h2>Login</h2>', inventory().replace('Plans Especials', 'New planning group'),
                     inventory().replace(link('MEMÒRIA', '/pe1.pdf'), ''),
                     inventory().replace('</div>', '<a rel="next" href="?page=2">Next</a></div>', 1),
                     inventory().replace('24.12.2002', '32.12.2002')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                PegoAyuntamientoAdapter.parse_projects(html)

    def test_stable_ids_and_reordering(self):
        rows = PegoAyuntamientoAdapter.parse_projects(inventory())
        changed = inventory().replace('MP 01: Mont Pego', 'MP 01: corrected description')
        self.assertEqual([r['id'] for r in rows],
                         [r['id'] for r in PegoAyuntamientoAdapter.parse_projects(changed)])

    def test_inventory_is_not_truncated(self):
        additions = ''.join('<h3>MP %02d: sector</h3>' % n + link('MEMÒRIA', '/m%d.pdf' % n)
                            for n in range(3, 103))
        html = inventory().replace('<h3>MP 02: carrer Vallet</h3>',
                                   additions + '<h3>MP 02: carrer Vallet</h3>')
        rows = PegoAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows), 105)
        self.assertIn('pego-proy-mp-102', {r['id'] for r in rows})

    def test_fetch_failure_preserves_previous_snapshot(self):
        adapter = PegoAyuntamientoAdapter()
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with patch('municipio.adapters.pego.urlopen', side_effect=OSError('unavailable')):
                with self.assertRaises(OSError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('pego')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, PegoAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 5}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('unused-state'))['rows'], 5)
            backfill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
