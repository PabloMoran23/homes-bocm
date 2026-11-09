import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

from municipio.adapters.gelida import GelidaAyuntamientoAdapter as Adapter, SOURCE, planning_title
from municipio.manifest import load_manifest


def inventory(title='POUM', suffix='poum', page_count=1):
    return f'''<div id="readspeakerPage"><h1>Planejament urbanístic i projectes</h1></div>
    <ul class="articlelist"><li class="article-item"><div class="tplDefault">
    <a href="{SOURCE}/{suffix}.html">{title}</a><div class="date">12/02/2015</div>
    </div></li></ul><ul class="paginacio"><li><a href="{SOURCE}">1</a></li>
    {f'<li><a href="{SOURCE}?pag=2">2</a></li>' if page_count > 1 else ''}
    <li>{page_count} pàgines</li></ul>'''


def detail(title='POUM', narrative=None):
    if narrative is None:
        narrative = "Aprovat definitivament per la Comissió d'Urbanisme de Barcelona el 29 de gener de 2015, i publicat en el DOGC a efectes d'executivitat el 5 de juny de 2015"
    return f'<main><div id="readspeakerPage"><h1>{title}</h1><div class="ddbbtext">{narrative}</div></div></main>'


class GelidaTests(unittest.TestCase):
    def test_dates_are_separate(self):
        entry = Adapter.parse_inventory(inventory())[0][0]
        row = Adapter.parse_detail(detail(), entry)
        self.assertEqual(row['fecha_publicacion'], '2015-02-12')
        self.assertEqual(row['fecha_aprob'], '2015-01-29')
        self.assertEqual(row['fecha_publicacion_dogc'], '2015-06-05')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])

    def test_documents_grouped_and_safelinks_retained(self):
        title = '260528_Modificació puntual del POUM'
        url = 'https://bpm.gelida.cat/OAC/download/abc'
        wrapped = 'https://esp01.safelinks.protection.outlook.com/?url=' + quote(url, safe='')
        html = detail(title, f'<a href="{wrapped}">Memòria</a><a href="{url}">Duplicate</a>')
        html = html.replace('</main>', '<div class="documents"><a href="/media/repository/plan.pdf">Plànols</a></div></main>')
        row = Adapter.parse_detail(html, Adapter.parse_inventory(inventory(title))[0][0])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], url)
        self.assertEqual(row['documentos'][0]['url_enlace_original'], wrapped)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])

    def test_exclusions(self):
        for title in ('Comunicació prèvia obres', 'Aprovació conveni Pla Parcial',
                      'Projecte reparcel·lació modificació POUM AGROPARC',
                      "Redacció d'un pla especial urbanístic", 'Estatuts PPr-4', 'Notícies'):
            self.assertFalse(planning_title(title), title)
        self.assertTrue(planning_title('Modificació Puntual del P.G.O.M.'))

    def test_fail_closed(self):
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<h1>Login</h1>')
        entry = Adapter.parse_inventory(inventory('Pla especial'))[0][0]
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail('Pla especial', 'sense documents'), entry)
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail('Other'), entry)

    def test_pagination_and_atomic_failure(self):
        adapter = Adapter('gelida')
        sources = {SOURCE: inventory(page_count=2), SOURCE + '?pag=2': inventory('Modificació POUM 3', 'mod3', 2),
                   SOURCE + '/poum.html': detail(), SOURCE + '/mod3.html': detail('Modificació POUM 3', '<a href="/media/repository/mod3.pdf">Pla</a>')}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len(path.read_text().splitlines()), 2)
            sources[SOURCE + '?pag=2'] = inventory('Modificació POUM 3', 'mod3', 3)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_bytes(), before)
            sources[SOURCE + '?pag=2'] = sources[SOURCE]
            with self.assertRaisesRegex(ValueError, 'Repeated inventory page'):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_bytes(), before)

    def test_manifest(self):
        manifest = load_manifest('gelida')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.config['ine_code'], '08091')


if __name__ == '__main__':
    unittest.main()
