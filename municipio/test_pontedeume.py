import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pontedeume import (
    SOURCE, PontedeumeAyuntamientoAdapter, group_instruments, parse_detail, parse_listing,
)
from municipio.manifest import load_manifest, load_yaml

TITLE = 'PUBLICACIÓN APROBACIÓN DEFINITIVA MODIFICACIÓN PUNTUAL PXOM URDI-2 LEITE CELTA'
NOTICE = '/sxc/es/informacion/tablon/2026/ANUNCIO_1.html'
DOC = '/sxc/export/sites/pontedeume/recursos/downloads/Tablon/2026/ANEXO.pdf'


def listing(title=TITLE, page=1, pages=(1,)):
    return (f'<div class="noticia"><h3><a href="{NOTICE}">URBANISMO</a></h3>'
            f'<p class="fecha">03/11/2026</p><p>{title}</p></div>'
            f'<div class="noticia"><p>Other notice page {page}</p></div>'
            '<div id="pagination">' + ''.join(
                f'<a href="{SOURCE}?page={p}">{p}</a>' for p in pages) + '</div>')


def detail(ref='2020/U032/000001'):
    return (f'<div class="article"><contenido>EXP: {ref}</contenido>'
            f'<div class="listado-pag"><a href="{DOC}" title="DOG">DOG</a></div></div>'
            f'<div class="listado-pag"><a href="{DOC.replace("ANEXO", "SELLADO_1")}">Sellado</a></div>')


class PontedeumeTests(unittest.TestCase):
    def test_manifest(self):
        manifest = load_manifest('pontedeume')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('15069', 'A Coruña'))
        self.assertFalse(raw['licencias']['enabled'])
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])

    def test_listing_selection_and_dates(self):
        notices, pages, count = parse_listing(listing(pages=(1, 2, 11)), SOURCE)
        self.assertEqual(count, 2)
        self.assertEqual(len(pages), 3)
        record = parse_detail(detail(), notices[0])
        row = group_instruments([record])[0]
        self.assertEqual(row['expediente'], '2020/U032/000001')
        self.assertEqual(row['fecha_publicacion'], '2026-11-03')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['tipo'], 'justificante_publicacion')
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)

    def test_excludes_forms_procurement_and_unrelated_plans(self):
        for title in ('Solicitude de aprobación PXOM', 'Licitación redacción PXOM',
                      'Modelo de licencia', 'Plan Xeral de prevención de riscos e anti-fraude',
                      'Convocatoria Premio Pontedeume en Obras', 'Oferta emprego arquitecto'):
            with self.subTest(title=title):
                self.assertEqual(parse_listing(listing(title), SOURCE)[0], [])

    def test_missing_or_offsite_content_fails(self):
        with self.assertRaises(ValueError):
            parse_listing('<html>Error</html>', SOURCE)
        with self.assertRaises(ValueError):
            parse_listing(listing().replace(SOURCE + '?page=1', 'https://example.org/?page=1'), SOURCE)
        notice = parse_listing(listing(), SOURCE)[0][0]
        for html in ('<div class="article">No expediente</div>',
                     '<div class="article">EXP: 2020/U032/000001</div>',
                     detail().replace(DOC, 'https://example.org/file.pdf')):
            with self.assertRaises(ValueError):
                parse_detail(html, notice)

    def test_grouping_by_source_reference_keeps_notice_provenance(self):
        notice = parse_listing(listing(), SOURCE)[0][0]
        first = parse_detail(detail(), notice)
        second = parse_detail(detail(), {**notice, 'url': notice['url'] + '?v=2',
                                        'fecha_publicacion': '2026-11-04'})
        third = parse_detail(detail('2021/U032/000002'), notice)
        rows = group_instruments([first, second, third])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['anuncios']), 2)
        self.assertEqual(len(rows[0]['documentos']), 4)
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-11-04')
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_crawler_follows_new_pages_and_update_is_full_refresh(self):
        adapter = PontedeumeAyuntamientoAdapter('pontedeume')
        pages = {SOURCE + '?page=1': listing(pages=(1, 2)),
                 SOURCE + '?page=2': listing('Unrelated', page=2, pages=(1, 2, 11)),
                 SOURCE + '?page=11': listing('Other unrelated', page=11, pages=(2, 11)),
                 'https://sede.pontedeume.gal' + NOTICE: detail()}
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            out = Path(folder) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(folder) / 'state.json')
            self.assertEqual(result['listing_pages'], 3)
            self.assertEqual(result['notices_scanned'], 6)
            self.assertEqual(len(fetch.call_args_list), 4)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '15069')

    def test_repeated_pages_and_empty_results_preserve_old_output(self):
        adapter = PontedeumeAyuntamientoAdapter('pontedeume')
        for html in (listing(pages=(1, 2)), listing('No instruments'),
                     '<p class="avisoNoticia">100 anuncios</p>' + listing()):
            with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', return_value=html):
                out = Path(folder) / 'proyectos.jsonl'
                out.write_text('existing\n')
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'existing\n')

    def test_licences_disabled_without_network(self):
        adapter = PontedeumeAyuntamientoAdapter('pontedeume')
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch') as fetch:
            out = Path(folder) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
