import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sallent import BASE, SOURCE, SallentAyuntamientoAdapter, _dates
from municipio.manifest import load_manifest, load_yaml

TITLE = '17a Modificació Puntual del POUM'
URL = BASE + '/17a-modificacio-puntual-del-poum'


def inventory(extra=''):
    return f'''<div class="bloc_servei"><h3>Notícies</h3><a href="/news">Projecte notícia</a></div>
    <div class="bloc_servei"><h3>Actuacions</h3>
    <a href="/17a-modificacio-puntual-del-poum">{TITLE}</a>
    <a href="/17a-modificacio-puntual-del-poum">{TITLE}</a>
    <a href="/form">Sol·licitud de llicència d'obres majors</a>
    <a href="/tender">Anunci de licitació</a><a href="/festival">Programa de festes</a></div>{extra}'''


def detail(narrative=''):
    return f'''<div id="contingut"><div id="contingut"><h1>{TITLE}</h1>
    <div class="info_contingut">{narrative}</div>
    <div class="espai_documents">
    <a href="/media/repository//plan.pdf">Memòria</a>
    <a href="/media/repository/plan.pdf">Memòria repetida</a>
    <a href="/media/repository/annex.pdf">Plànols suspensió llicències</a></div>
    <div class="mes_info"><a href="/another-plan">Another instrument</a></div>
    <div class="info_actualitzacio"><span class="data">30-09-2026 10:06</span></div>
    </div></div>'''


class SallentTests(unittest.TestCase):
    def test_inventory_scope_and_deduplication(self):
        self.assertEqual(SallentAyuntamientoAdapter.parse_inventory(inventory()), {URL: TITLE})
        for html in ['<h1>Login</h1>', inventory('<a href="?page=2" rel="next">Next</a>'),
                     inventory('<ul class="pagination"><li><a href="?page=2">2</a></li></ul>')]:
            with self.assertRaises(ValueError):
                SallentAyuntamientoAdapter.parse_inventory(html)

    def test_group_documents_without_related_links_or_invented_dates(self):
        row = SallentAyuntamientoAdapter.parse_detail(detail(), URL, TITLE)
        self.assertEqual(len(row['documentos']), 2)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['source_updated_at_text'], '30-09-2026 10:06')
        self.assertEqual(row['id'], SallentAyuntamientoAdapter.parse_detail(detail('Changed text'), URL, TITLE)['id'])

    def test_explicit_date_semantics(self):
        cases = [
            ("El POUM va ser aprovat per la Comissió Territorial en sessió de 19 de maig de 2010, i publicat al DOGC núm. 5672 de 16 de juliol de 2010.", ('2010-05-19', '2010-07-16')),
            ("La sessió celebrada el dia 6 de febrer de 2024 va prendre l'acord d'aprovar definitivament la Modificació. Es va publicar l'acord al DOGC del dia 20 de març de 2024.", ('2024-02-06', '2024-03-20')),
            ("En data 7 de març de 2023, es va publicar al DOGC l'acord d'aprovació inicial.", (None, '2023-03-07')),
            ("La Junta celebrada el dia 25 de juny 2024, va acordar aprovar inicialment la Modificació.", ('2024-06-25', None)),
            ("Va ser aprovada definitivament pel conseller en data 13 d'abril de 2015 i publicada al DOGC núm.6998 del dia 16 de novembre de 2015.", ('2015-04-13', '2015-11-16')),
            ("A partir del dia 17 de juny de 2020 és vigent el Pla Especial.", (None, None)),
            ("El Ple celebrat el dia 31 de febrer de 2024, es va acordar aprovar inicialment el Pla.", (None, None)),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(_dates(text), expected)

    def test_fail_closed_details(self):
        for html in ['<h1>Login</h1>', detail().replace(TITLE, 'Other plan'),
                     f'<div id="contingut"><h1>{TITLE}</h1><a href="/form">Form</a></div>']:
            with self.assertRaises(ValueError):
                SallentAyuntamientoAdapter.parse_detail(html, URL, TITLE)

    def test_snapshot_and_failure_preserves_existing_output(self):
        adapter = SallentAyuntamientoAdapter('sallent')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail()]):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            before = path.read_text()
            self.assertEqual(json.loads(before)['codigo_ine'], '08191')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), '<h1>Error</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'lic.jsonl')['status'], 'disabled')

    def test_manifest_and_municipality(self):
        manifest = load_manifest('sallent')
        self.assertEqual((manifest.nombre, manifest.provincia), ('Sallent', 'Barcelona'))
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08191')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(ValueError):
            SallentAyuntamientoAdapter('sallent', {'ine_code': '08190'})


if __name__ == '__main__':
    unittest.main()
