import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.zizur_mayor import (
    EXPOSURE, INVENTORY, ZizurMayorAyuntamientoAdapter, parse_exposure, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def wrap(body):
    return '<main><div class="contenido content">' + body + '</div></main>'


def link(title, filename):
    return f'<a href="/wp-content/uploads/{filename}.pdf">{title}</a>'


INVENTORY_HTML = wrap('''
<p><strong>PLAN MUNICIPAL:</strong></p><ul><li>'''
    + link('Memoria Texto Refundido 2011', 'mem') + '''</li></ul>
<p><strong>PLAN PARCIAL DEL SECTOR ARDOI:</strong></p><ul><li>'''
    + link('Normativa I', 'norm') + '''</li><li>'''
    + link('Modificación Plan Parcial Ardoi: H-6', 'h6') + '''<br>
Publicada en el BON nº 28, de 11 de febrero de 2013.
<ul><li>''' + link('Modificación Plan Parcial Ardoi: Unidad Morfológica M-8', 'm8')
    + link('SITUACION', 'situacion') + link('SITUACION', 'situacion') + '''<br>
Publicado en el BON nº 176, de 12 de septiembre de 2013.</li></ul></li></ul>''')
EXPOSURE_HTML = wrap('''<div><p><strong>Aprobación inicial del Plan Urbanístico Municipal (PUM) de Zizur Mayor</strong></p>
<p>Aprobado por acuerdo adoptado por el Pleno en sesión de fecha 25 de agosto de 2026, conforme a la ley de 26 de julio de 2017.</p>
<ul><li>''' + link('Memoria informativa', 'mem-info') + '</li><li>'
    + link('Planos ordenación', 'planos') + '</li></ul></div>')


class ZizurMayorTests(unittest.TestCase):
    def test_nested_modifications_own_their_documents_and_dates(self):
        rows = parse_inventory(INVENTORY_HTML)
        self.assertEqual(len(rows), 4)
        base, ardoi, h6, m8 = rows
        self.assertEqual(len(base['documentos']), 1)
        self.assertEqual(len(ardoi['documentos']), 1)
        self.assertEqual(len(h6['documentos']), 1)
        self.assertEqual(len(m8['documentos']), 2)
        self.assertEqual(h6['fecha_publicacion'], '2013-02-11')
        self.assertEqual(m8['fecha_publicacion'], '2013-09-12')
        self.assertNotIn('fecha_acuerdo', h6)
        self.assertNotIn('fecha_publicacion', base)
        self.assertNotIn('fecha_aprob', base)
        self.assertTrue(m8['documentos'][0]['url'].startswith('https://www.zizurmayor.es/'))
        reordered = INVENTORY_HTML.replace(link('SITUACION', 'situacion'), link('Plano situación', 'situacion'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in parse_inventory(reordered)])

    def test_pum_groups_annexes_and_uses_only_explicit_agreement(self):
        rows = parse_exposure(EXPOSURE_HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['fecha_acuerdo'], '2026-08-25')
        self.assertEqual(row['fase'], 'aprobacion_inicial')
        self.assertEqual(len(row['documentos']), 2)
        self.assertNotIn('fecha_publicacion', row)
        self.assertNotIn('lat', row)

    def test_reject_pagination_empty_changed_and_untrusted_sources(self):
        for html in [wrap(''), INVENTORY_HTML + '<a rel="next" href="?page=2">2</a>',
                     INVENTORY_HTML.replace('PLAN MUNICIPAL:', 'Otro plan:'),
                     INVENTORY_HTML.replace('/wp-content/uploads/mem.pdf', 'https://example.org/mem.pdf')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_exposure(EXPOSURE_HTML.replace('por acuerdo adoptado', 'propuesta'))

    def test_live_path_atomic_output_and_disabled_licences(self):
        adapter = ZizurMayorAyuntamientoAdapter('zizur-mayor')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY_HTML, EXPOSURE_HTML]) as fetch:
                result = adapter.backfill_proyectos(out)
                self.assertEqual([c.args[0] for c in fetch.call_args_list], [INVENTORY, EXPOSURE])
            self.assertEqual(result['count'], 5)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 5)
            previous = out.read_text()
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY_HTML, wrap('')]):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), previous)
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_manifest_safety_and_identity(self):
        manifest = load_manifest('zizur-mayor')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '31907')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
