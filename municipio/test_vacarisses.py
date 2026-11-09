"""Offline semantic and crawl-boundary regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vacarisses import SOURCE, VacarissesAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def detail(body, docs, heading='Sector de prova'):
    links = ''.join(f'<a href="/media/{i}.pdf">{label}</a>' for i, label in enumerate(docs))
    return f'<div id="readspeakerPage"><h1>{heading}</h1><div class="ddbbtext">{body}</div><span class="updated">Darrera actualització: 27.03.2026 | 16:23</span></div><section id="page-documents">{links}</section>'


BODY = "La Junta de Govern Local del 9 de març de 2026 va aprovar el projecte d'urbanització. En la mateixa sessió va aprovar el projecte de reparcel·lació."
DOCS = ["Anunci d'aprovació inicial del projecte d'urbanització (126KB)", "Projecte d'urbanització (35MB)", "Anunci d'aprovació inicial del projecte de reparcel·lació", 'Projecte de reparcel·lació']
INVENTORY = '<div id="readspeakerPage"><h1>Urbanisme</h1><ul class="widgetMenu"><a href="/ajuntament/normativa/urbanisme/sector">Sector</a><a href="/ajuntament/normativa/urbanisme/sector">Sector</a></ul></div>'


class VacarissesTests(unittest.TestCase):
    def test_group_instruments_and_dates(self):
        rows = Adapter.parse_detail(detail(BODY, DOCS), SOURCE + '/sector')
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(len({r['id'] for r in rows}), 2)
        for row in rows:
            self.assertEqual(row['fecha_acuerdo'], '2026-03-09')
            self.assertEqual(row['fecha_actualizacion_fuente'], '2026-03-27')
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['lat'])
            self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(rows, Adapter.parse_detail(detail(BODY, DOCS), SOURCE + '/sector'))

    def test_single_instrument_generic_announcement(self):
        rows = Adapter.parse_detail(detail(BODY.split(' En la mateixa')[0], ['Anunci d’aprovació inicial', "Projecte d'urbanització"]), SOURCE + '/pou')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_ventayol_legal_dates_not_agreement(self):
        body = 'Decret 1/2010, de 3 d’agost. Junta de Govern Local, reunida en sessió ordinària el dia 28 de setembre de 2026, va aprovar inicialment les obres d’urbanització “PROJECTE DE REPARCEL·LACIÓ EL VENTAYOL”'
        rows = Adapter.parse_detail(detail(body, ['Memòria', 'Documentació gràfica']), SOURCE + '/ventayol')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tipo'], 'reparcelacion')
        self.assertEqual(rows[0]['fecha_acuerdo'], '2026-09-28')
        self.assertIn('source_warning', rows[0])

    def test_detail_study_is_not_a_building_licence(self):
        body = "La Junta de Govern Local, reunida en sessió ordinària el 11 de maig de 2026, va aprovar inicialment la Modificació de l'Estudi de Detall per 9 habitatges."
        row, = Adapter.parse_detail(detail(body, ['Anunci', 'Estudi de detall']), SOURCE + '/manresa')
        self.assertEqual(row['tipo'], 'estudi_detall')
        self.assertEqual(row['fecha_acuerdo'], '2026-05-11')

    def test_missing_date_not_synthesized(self):
        row, = Adapter.parse_detail(detail("Junta de Govern Local va aprovar el projecte d'urbanització", ["Projecte d'urbanització"]), SOURCE + '/sector')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fase'])

    def test_inventory_deduplicates_responsive_menus(self):
        self.assertEqual(Adapter.parse_inventory(INVENTORY), [SOURCE + '/sector'])

    def test_pagination_fails_instead_of_truncating(self):
        for extra in ['<a rel="next" href="?page=2">2</a>', '<div class="pagination">2</div>', '<a href="?page=2">Següent</a>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(INVENTORY + extra)

    def test_no_forms_news_or_missing_documents(self):
        for html in ['<h1>Login</h1>', detail('Sol·licitud de llicència', ['Formulari']), detail(BODY, []), detail(BODY, DOCS + ['Unrelated document'])]:
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, SOURCE + '/sector')

    def test_failed_detail_preserves_previous_snapshot(self):
        adapter = Adapter('vacarisses')
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, '<h1>Login</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_snapshot_update_and_manifest(self):
        manifest = load_manifest('vacarisses')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        adapter = Adapter('vacarisses')
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, detail(BODY, DOCS)]):
                result = adapter.update_proyectos(output, Path(td) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
