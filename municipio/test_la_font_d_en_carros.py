import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_font_d_en_carros import (
    SOURCE, LaFontDEnCarrosAyuntamientoAdapter, enrich_notice, parse_inventory,
)
from municipio.manifest import load_manifest


def viewer(titles):
    return '<main>' + ''.join(
        '<button class="doc-viewer__btn" data-wp-context="' + html.escape(json.dumps({
            'title': title, 'pdfUrl': 'https://transparencia.lafontdencarros.es/wp-content/uploads/2026/06/' + str(i) + '.pdf',
        }), quote=True) + '"></button>' for i, title in enumerate(titles)) + '</main>'


class PlanningTests(unittest.TestCase):
    def test_groups_documents_not_download_links(self):
        titles = ['1. Informació pública pla general juliol 2018',
                  '2. Aprovació provisional pla general abril 2019',
                  'Planol classificació concert previ',
                  'Ordenació altures edificació part 1',
                  'Ordenació altures edificació part 2',
                  'Normes subsidiaries', 'Ordenances pla parcial Tossal Gros',
                  'Pla especial de protecció del recinte emmurallat',
                  "Plà d'actuació municipal enfront del risc sismic",
                  'Sol·licitud llicència obra major', 'Anunci licitació obres']
        rows, excluded = parse_inventory(viewer(titles))
        self.assertEqual(len(rows), 5)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2, 1, 1, 1])
        self.assertEqual(len(excluded), 3)
        self.assertTrue(all(r['fecha_aprob'] is None and r['geometry'] is None for r in rows))
        # Identity survives reordering of the document list.
        reordered, _ = parse_inventory(viewer(list(reversed(titles))))
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in reordered})

    def test_missing_inventory_and_pagination_fail(self):
        for source in ['<h1>Urbanisme</h1><a href="form.pdf">Formulari</a>',
                       viewer(['Normes subsidiaries']) + '<a rel="next" href="?page=2">Next</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(source)

    def test_untrusted_document_url_fails(self):
        source = viewer(['Normes subsidiaries']).replace('transparencia.lafontdencarros.es', 'example.org')
        with self.assertRaises(ValueError):
            parse_inventory(source)

    def test_notice_dates_and_document_links(self):
        row = {'fecha_publicacion': None}
        public = {'titulo': '1. Informació pública pla general juliol 2018'}
        enrich_notice(row, public, 'INFORMACIÓ PÚBLICA DEL PLA GENERAL DE LA FONT D’EN CARRÒS. '
                      'El Ple en sessió de 12 de juliol de 2018 va aprovar l’exposició. '
                      'Publicat al DOCV de 30 de juliol de 2018. https://www.dogv.gva.es/va/resultat-dogv?signatura=2018/7032')
        self.assertEqual(public['fecha_acuerdo'], '2018-07-12')
        self.assertEqual(public['fecha_publicacion'], '2018-07-30')
        provisional = {'titulo': '2. Aprovació provisional pla general abril 2019'}
        enrich_notice(row, provisional, 'APROVACIÓ PROVISIONAL DEL PLA GENERAL DE LA FONT D’EN CARRÒS. '
                      'El Ple en sessió d’11 d’abril de 2019 va aprovar provisionalment el pla. '
                      'https://drive.google.com/file/d/certificat/view?usp=sharing')
        self.assertEqual(row['fecha_aprob'], '2019-04-11')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(len(provisional['enlaces_documentacion']), 1)
        self.assertIn('provisional', row['fase'])

    def test_missing_dates_are_not_invented(self):
        row = {'fecha_aprob': None, 'fecha_publicacion': None}
        doc = {'titulo': 'Pla especial de protecció del recinte emmurallat'}
        enrich_notice(row, doc, 'Pla Especial de Protecció del Recinte Emmurallat de la Font d’en Carròs')
        self.assertIsNone(row['fecha_aprob'])
        enrich_notice(row, doc, 'Pla Especial de Protecció del Recinte Emmurallat de la Font d’en Carròs. '
                      'Pla aprovat pel plenari en sessió de 12 de novembre de 2020.')
        self.assertEqual(row['fecha_aprob'], '2020-11-12')
        self.assertNotIn('definitiva', row['fase'].split('(')[0])

    def test_failed_snapshot_preserves_previous_output(self):
        adapter = LaFontDEnCarrosAyuntamientoAdapter('la-font-d-en-carros')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_get', side_effect=[
                viewer(['2. Aprovació provisional pla general abril 2019']).encode(),
                RuntimeError('network error'),
            ]):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_contract(self):
        manifest = load_manifest('la-font-d-en-carros')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertEqual(manifest.portal.config['ine_code'], '46127')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
