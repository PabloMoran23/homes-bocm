import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.calamocha import CalamochaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(kind, links, extra=''):
    heading = 'Documentos' if kind == 'documentos' else 'Modificaciones'
    return '<div id="content"><h2>P.G.O.U. ' + heading + '</h2><ul>' + ''.join(
        '<li><a href="/wp-content/uploads/2021/03/' + url + '">' + title + '</a></li>'
        for title, url in links) + '</ul>' + extra + '</div>'


class CalamochaTests(unittest.TestCase):
    def test_group_documents_and_keep_provenance(self):
        html = page('modificaciones', [('Modificación puntual nº 9. Memoria', 'mem.pdf'),
                                      ('Modificación puntual nº 9. Plano vigente', 'old.pdf'),
                                      ('Modificación puntual nº 8. Estación eléctrica bis', 'bis.pdf'),
                                      ('Modificación puntual nº 9. Memoria', 'mem.pdf')])
        rows = parse_inventory(html, 'modificaciones')
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['id'], 'calamocha-pgou-modificacion-9')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fase'])
        self.assertIsNone(rows[0]['geometry'])
        self.assertEqual(rows[0]['documentos'][1]['titulo'], 'Modificación puntual nº 9. Plano vigente')

    def test_base_plan_is_one_instrument(self):
        rows = parse_inventory(page('documentos', [('Normativa urbanística', 'norm.pdf'),
                                                   ('Plano Collados', 'collados.pdf')]), 'documentos')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '44050')

    def test_fail_closed_for_changed_sources(self):
        good = page('documentos', [('Normativa', 'a.pdf')])
        for html in ['', page('documentos', []), good + '<a rel="next" href="/page/2">2</a>',
                     good + '<div class="page-numbers">2</div>',
                     good.replace('</ul>', '</ul><a href="/2">Siguiente</a>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, 'documentos')
        with self.assertRaises(ValueError):
            parse_inventory(page('modificaciones', [('Solicitud de licencia', 'form.pdf')]), 'modificaciones')

    def test_manifest_registry_refresh_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('calamocha'))
        fixtures = {'documentos': page('documentos', [('Normativa', 'a.pdf')]),
                    'modificaciones': page('modificaciones', [('Modificación puntual nº 1', '1.pdf')])}
        with tempfile.TemporaryDirectory() as directory, patch.object(CalamochaAyuntamientoAdapter, '_fetch', side_effect=lambda k: fixtures[k]):
            out = Path(directory) / 'projects.jsonl'
            adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            before = out.read_text()
            with patch.object(CalamochaAyuntamientoAdapter, '_fetch', return_value='broken'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'lic.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
