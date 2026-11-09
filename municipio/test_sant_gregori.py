"""Offline parser and adapter contract tests; no live source required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_gregori import (
    SantGregoriAyuntamientoAdapter, SOURCES, catalan_date, parse_inventory, parse_poum,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(heading, body, attachments=''):
    return f'<div><div><h1>{heading}</h1></div><div class="text">{body}</div>{attachments}</div>'


TITLE = 'Projecte constructiu per la connectivitat entre les rutes de la Vall del Ter i de la Vall de Llémena'
PUBLIC_TITLE = 'Pla Parcial Urbanístic SUD 1 Sant Gregori - Dades protegides'
PUBLIC = page('Projectes a exposició pública', f'<p><a href="https://docs.hoobaweb.com/1422/plan.pdf">{PUBLIC_TITLE}</a> (Aprovat inicialment per la Junta de Govern local del 30 de juny de 2025)</p>')
FINAL = page('Projectes definitius', f'<p><strong>{TITLE}</strong> (Aprovat definitivament pel Ple en sessió de 18 de gener de 2021)</p>', f'<a href="https://docs.hoobaweb.com/1422/work.pdf">{TITLE} (PDF)</a><a href="https://docs.hoobaweb.com/1422/report.pdf">Informe sobre el {TITLE.lower()}</a>')
POUM = page('POUM', '<p>La Comissió en sessió de 21 de juliol de 2010 va acordar aprovar definitivament el POUM de Sant Gregori.</p><p>Va entrar en vigor el dia següent de la seva publicació (<a href="https://dogc.gencat.cat/ca/document-del-dogc/?documentId=575828">DOGC</a> núm. 5841 de 21/03/2011).</p>')
DOCUMENTS = '<div><div><div><h1>Memòria i documentació</h1></div></div><div><a href="https://docs.hoobaweb.com/1422/plan.pdf">Normes urbanístiques</a><a href="https://docs.hoobaweb.com/1422/plan.pdf">Normes (PDF)</a></div></div>'


class SantGregoriTests(unittest.TestCase):
    def test_public_plan_and_dates(self):
        row, = parse_inventory(PUBLIC, 'publica')
        self.assertEqual(row['fecha_acuerdo'], '2025-06-30')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['lat'])
        self.assertEqual(row['codigo_ine'], '17163')
        self.assertFalse(row['publication_ready'])

    def test_work_and_report_are_one_record(self):
        row, = parse_inventory(FINAL, 'definitius')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2021-01-18')
        self.assertEqual(row['titulo'], TITLE)
        self.assertTrue(all(d['source_url'] == SOURCES['definitius'] for d in row['documentos']))

    def test_poum_document_group_and_date_semantics(self):
        row = parse_poum(POUM, DOCUMENTS)
        self.assertEqual(len(row['documentos']), 2)  # duplicate PDF + gazette
        self.assertEqual(row['fecha_aprob'], '2010-07-21')
        self.assertEqual(row['fecha_publicacion'], '2011-03-21')
        self.assertIsNone(row['fecha'])

    def test_missing_day_does_not_become_first_day(self):
        row, = parse_inventory(PUBLIC.replace('30 de juny de 2025', 'juny de 2025'), 'publica')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertEqual(catalan_date("9 d’octubre de 2019"), '2019-10-09')
        with self.assertRaises(ValueError):
            catalan_date('31 de febrer de 2025')

    def test_navigation_forms_news_and_wrong_source_rejected(self):
        for body in ['<a href="form.pdf">Sol·licitud de llicència</a>',
                     '<p>Notícia de licitació de les obres</p>', '<p>POUM</p>']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_inventory(page('Projectes definitius', body), 'definitius')
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Login</h1>', 'publica')

    def test_pagination_unassigned_documents_and_missing_poum_rejected(self):
        for html in [FINAL.replace('</div>', '<nav class="pagination">2</nav></div>', 1),
                     FINAL.replace('</div>', '<a href="extra.pdf">Unassigned project</a></div>', 1),
                     FINAL.replace('Aprovat definitivament', 'En estudi')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, 'definitius')
        with self.assertRaises(ValueError):
            parse_poum(POUM.replace('va acordar aprovar definitivament', 'va estudiar'), DOCUMENTS)

    def test_complete_refresh_and_failure_preserve_previous_output(self):
        fixtures = dict(publica=PUBLIC, definitius=FINAL, poum=POUM, documents=DOCUMENTS)
        adapter = SantGregoriAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda key: fixtures[key]):
            target = Path(tmp) / 'projects.jsonl'
            result = adapter.backfill_proyectos(target)
            before = target.read_text()
            self.assertEqual(result['rows'], 3)
            adapter.update_proyectos(target, Path(tmp) / 'state.json')
            self.assertEqual(target.read_text(), before)
            self.assertEqual(len({json.loads(line)['id'] for line in before.splitlines()}), 3)
            fixtures['poum'] = '<h1>Unavailable</h1>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(target)
            self.assertEqual(target.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest_loads_through_registry(self):
        manifest = load_manifest('sant-gregori')
        self.assertIsInstance(load_portal_adapter(manifest), SantGregoriAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Girona')


if __name__ == '__main__':
    unittest.main()
