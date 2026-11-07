import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.castell_d_aro_platja_d_aro_i_s_agaro import (
    SOURCE, SLUG, parse_inventory, parse_detail,
    CastellDAroPlatjaDAroISAgaroAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest

TITLE = 'Modificació puntual núm. 15 del POUM – Zona Industrial'
URL = SOURCE + 'modificacio-puntual-num-15/'
ITEM = {'titulo': TITLE, 'url': URL}
DOC = 'https://ciutada.platjadaro.com/wp-content/uploads/2024/12/cert-30062026.pdf'
INVENTORY = f'''<main><div class="vc_tta-panel"><span class="vc_tta-title-text">En tràmit</span>
<div class="planejament-urbanist-list"><a href="{URL}"><div class="main"><p>{TITLE}</p></div>
<em>News and document excerpt must not become the title</em></a></div></div></main>'''
DETAIL = f'''<main><article class="type-planejament_urbanist"><div class="planejament_urbanistic">
<h3>{TITLE}</h3><div class="badge-aro">Planejament en tràmit</div><p>Real instrument description.</p>
<a href="https://bpm.platjadaro.cat/OAC/download/project-id">Projecte</a>
<article><div class="row"><div class="label"><h4>Aprovació inicial</h4></div>
<div class="data">23/02/2026</div><div class="docs"><a href="{DOC}">ANUNCI DOGC DE 03.03.2026</a></div></div></article>
<article><div class="row"><div class="label"><h4>Aprovació provisional</h4></div>
<div class="data">29/06/2026</div><div class="docs"><a href="{DOC}">CERTIFICAT 30-06-2026</a></div></div></article>
</div></article></main>'''


class PlanningTests(unittest.TestCase):
    def test_inventory_scope_dedup_and_exclusion(self):
        html = INVENTORY.replace('</main>', '<a href="/licencia">Formulari llicència</a></main>')
        self.assertEqual(parse_inventory(html), [ITEM])
        card = '<div class="planejament-urbanist-list">' + INVENTORY.split('<div class="planejament-urbanist-list">')[1].split('</div></div></main>')[0] + '</div>'
        # Repeated links to the same instrument do not produce extra projects.
        repeated = INVENTORY.replace('</div></div></main>', '</div>' + card + '</div></main>')
        self.assertEqual(parse_inventory(repeated), [ITEM])

    def test_dates_grouping_and_identity(self):
        row = parse_detail(DETAIL, ITEM)
        self.assertEqual(row['fecha_acuerdo'], '2026-06-29')
        self.assertEqual(row['fase'], 'aprobación provisional')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['hitos']), 2)
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['url'], DOC)
        self.assertEqual(row['id'], parse_detail(DETAIL.replace('29/06/2026', '28/06/2026'), ITEM)['id'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        alternate = 'https://bpm.platjadaro.cat/download4j/download/certificate.pdf?id=uniqueid'
        self.assertEqual(parse_detail(DETAIL.replace(DOC, alternate), ITEM)['documentos'][1]['url'], alternate)

    def test_fail_closed_inventory(self):
        for html in ['<main>Login or news</main>', INVENTORY.replace('En tràmit', 'Vigent'),
                     INVENTORY + '<div class="pagination">2</div>',
                     INVENTORY.replace('</main>', '<button>Carrega més</button></main>'),
                     INVENTORY.replace(URL, 'https://example.org/project')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_fail_closed_detail(self):
        for html in ['<main>Licence application form</main>',
                     DETAIL.replace(TITLE, 'Other instrument'),
                     DETAIL.replace(DOC, 'https://example.org/attachment.pdf'),
                     DETAIL.replace('29/06/2026', '31/02/2026'),
                     DETAIL.replace('Aprovació provisional', 'Data de publicació'),
                     DETAIL.replace('Planejament en tràmit', 'Planejament vigent')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, ITEM)

    def test_snapshot_update_and_failure_preserves_output(self):
        adapter = Adapter()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, DETAIL]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '17048')
            previous = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, '<main>Login</main>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)
            with patch.object(adapter, '_fetch', side_effect=AssertionError('Licence network request')):
                self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest(SLUG)
        self.assertEqual(manifest.nombre, "Castell d'Aro, Platja d'Aro i s'Agaró")
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.config['ine_code'], '17048')


if __name__ == '__main__':
    unittest.main()
