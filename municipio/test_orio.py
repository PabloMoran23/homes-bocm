import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.orio import OrioAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest


def item(ident='10', title='Hiri Antolamenduko Plan Orokorra 2023', body=None):
    body = body or '''<p>Orioko Udalak 2022ko abenduaren 22ko udalbatzarrean eman zion lehen onarpena Orioko Hiri Antolamenduko Plan Orokorrari.</p>
      <a href="/wp-content/uploads/plan.pdf">Memoria</a>
      <a href="/wp-content/uploads/plan.pdf">Memoria</a>
      <a href="/wp-content/uploads/annex.pdf">Anexo</a>'''
    return f'''<div class="accordion-item"><h2 class="accordion-header">{title}</h2>
      <article class="espe" id="{ident}"><span class="hasiera">2023/01/19</span>
      <span class="amaiera">2023/03/31</span><div class="card-content">{body}</div></article></div>'''


class OrioTests(unittest.TestCase):
    def test_grouping_dates_and_exclusions(self):
        rows = OrioAyuntamientoAdapter.parse_inventory(item() + item() + item('11', 'Erabilera turistikoak erregulatzeko ordenantza'))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2022-12-22')
        self.assertEqual(row['fecha_inicio_exposicion'], '2023-01-19')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['codigo_ine'], '20061')

    def test_other_instruments_have_no_implied_approval(self):
        rows = OrioAyuntamientoAdapter.parse_inventory(item('20', 'HAPOaren aldaketa puntuala Dike-Kofradia eremu ez-jarraituan', '<a href="/wp-content/uploads/dike.pdf">Plan</a>') + item('30', 'HAPOko hiri-eremuen zonako plana'))
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertNotIn('fase', rows[0])
        self.assertEqual(rows[1]['tipo'], 'plan_zonal_acustico')

    def test_fail_closed(self):
        for html in ['', item(body='<p>No documents</p>'), item() + '<a rel="next" href="https://other.example/page/2/">2</a>', item() + '<button>Gehiago kargatu</button>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                OrioAyuntamientoAdapter.parse_inventory(html)

    def test_pagination_is_followed_and_deduplicated(self):
        first = Mock(url=SOURCE, text=item() + '<link rel="next" href="/espedienteak/page/2/">')
        second = Mock(url=SOURCE + 'page/2/', text=item() + item('20', 'HAPOaren aldaketa puntuala Dike'))
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.orio.requests.get', side_effect=[first, second]) as get:
            result = OrioAyuntamientoAdapter('orio').backfill_proyectos(Path(tmp) / 'out.jsonl')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(get.call_count, 2)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.orio.requests.get', return_value=first):
            with self.assertRaises(ValueError):
                OrioAyuntamientoAdapter('orio').backfill_proyectos(Path(tmp) / 'out.jsonl')

    def test_fetch_refresh_and_disabled_licences(self):
        response = Mock(url=SOURCE, text=item(), content=item().encode())
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.orio.requests.get', return_value=response):
            adapter = OrioAyuntamientoAdapter('orio')
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json')['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'orio-proy-10')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        manifest = load_manifest('orio')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Gipuzkoa')


if __name__ == '__main__':
    unittest.main()
