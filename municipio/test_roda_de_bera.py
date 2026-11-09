"""Parser contracts using small municipal markup fixtures; no network needed."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.roda_de_bera import RodaDeBeraAyuntamientoAdapter as Adapter, SOURCES
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(title='Exp. 2648/2024. Projecte de telelectura', pagination=''):
    return f'''<main><table class="com-content-category__table"><tbody><tr>
    <th class="list-title"><a href="{SOURCES[0]}/8010-projecte">{title}</a></th>
    </tr></tbody></table><div class="pagination">{pagination}</div></main>'''


def detail(title='Exp. 2648/2024. Projecte de telelectura', link='pla.pdf'):
    return f'''<main><div class="com-content-article"><h1>{title}</h1>
    <div class="com-content-article__body"><p>Memòria i plànols</p>
    <a href="/uploads/{link}">Projecte</a><a href="/uploads/{link}">Còpia</a>
    <a href="/noticies/licitacio">Licitació</a></div></div></main>'''


class RodaDeBeraTests(unittest.TestCase):
    def entry(self):
        return Adapter.parse_inventory(inventory(), SOURCES[0], SOURCES[0])[0][0]

    def test_pagination_collects_numeric_next_and_last_without_duplicates(self):
        html = inventory(pagination=''.join(f'<a href="?start={n}">{label}</a>' for n,label in [(25,'2'),(25,'Següent'),(125,'Darrera')]) + '<a href="#">1</a>')
        entries, pages = Adapter.parse_inventory(html, SOURCES[0], SOURCES[0])
        self.assertEqual(len(entries), 1)
        self.assertEqual(set(pages), {SOURCES[0]+'?start=25', SOURCES[0]+'?start=125'})

    def test_bad_pagination_fails_instead_of_truncating(self):
        for href in ['https://example.org/?start=25', '?page=2', '?start=bad']:
            with self.subTest(href=href), self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory(pagination=f'<a href="{href}">Next</a>'), SOURCES[0], SOURCES[0])

    def test_form_or_changed_inventory_rejected(self):
        for html in ['<main>Login</main>', inventory('Sol·licitud de llicència'), inventory().replace('<tbody>', '<tbody><tr><td>broken</td></tr>')]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html, SOURCES[0], SOURCES[0])

    def test_documents_provenance_and_no_inferred_dates(self):
        row = Adapter.parse_detail(detail(), self.entry())
        self.assertEqual(row['codigo_ine'], '43131')
        self.assertEqual(len(row['documentos']), 1)
        self.assertEqual(row['documentos'][0]['pagina_origen'], row['url'])
        for field in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_group_instrument_preserves_all_articles_and_documents(self):
        first = Adapter.parse_detail(detail(), self.entry())
        entry = {**self.entry(), 'url': SOURCES[0]+'/7984-digitalitzacio'}
        second = Adapter.parse_detail(detail(link='memoria.pdf'), entry)
        grouped = Adapter.group_projects([first, second])
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]['documentos']), 2)
        self.assertEqual(len(grouped[0]['fuentes']), 2)

    def test_year_typo_not_repaired(self):
        title='Exp. 3714/202. Projecte cuina Casal'
        entry=Adapter.parse_inventory(inventory(title), SOURCES[0], SOURCES[0])[0][0]
        self.assertEqual(Adapter.parse_detail(detail(title),entry)['expediente'], '3714/202')

    def test_missing_docs_or_mismatched_article_fails(self):
        for html in [detail().replace('/uploads/pla.pdf','/noticies/licitacio'), detail('Exp. 999/2024. Projecte diferent'), '<main>error</main>']:
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, self.entry())

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('roda-de-bera')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_update_is_complete_snapshot(self):
        adapter=Adapter('roda-de-bera')
        with patch.object(adapter,'backfill_proyectos',return_value={'rows':3}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('out'),Path('state')), {'rows':3})
            backfill.assert_called_once_with(Path('out'))

    def test_repeated_pages_fail_without_replacing_output(self):
        class Response:
            def __init__(self,url): self.url=url
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def raise_for_status(self): pass
            def iter_content(self, size):
                yield inventory(pagination='<a href="?start=25">2</a>').encode()
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'proyectos.jsonl';out.write_text('previous snapshot')
            with patch('municipio.adapters.roda_de_bera.requests.Session.get', side_effect=lambda url,**kwargs:Response(url)):
                with self.assertRaisesRegex(ValueError,'Repeated inventory page'):
                    Adapter('roda-de-bera').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
