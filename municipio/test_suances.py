import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.suances import (
    PGOU_URL, REGISTER_URL, WORKS_URL, SuancesAyuntamientoAdapter,
    parse_planning, parse_works,
)
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return '<div data-elementor-type="wp-page">' + body + '</div>'


PLANS = page(f'''
<h2>PGOU - VIGENTE</h2><a href="{REGISTER_URL}">Documentación completa</a>
<h2>Avance aprobación inicial nuevo PGOU (no vigente)</h2>
<a href="#random-collapse-123">2. MEMORIA</a>
<a href="https://suancesurbanismo.atys.net/plan/memoria.pdf">Memoria</a>
<a href="https://suancesurbanismo.atys.net/plan/normas.pdf">Normativa</a>
<a href="https://suancesurbanismo.atys.net/plan/form.pdf">Instancia</a>
<h2>Informe sostenibilidad</h2>
<a href="https://suancesurbanismo.atys.net/plan/ambiental.pdf">Memoria</a>
''')


def card(title='Reurbanización Calle Piélagos'):
    return f'''<div class="elementskit-card"><span class="ekit-accordion-title">{title}</span>
<div class="elementskit-card-body">El proyecto contempla la renovación de las redes de abastecimiento y
saneamiento de agua de toda la calle, con obras de pavimentación y mobiliario urbano.
<a href="/wp-content/uploads/calle.jpg"><img alt="Plano calle"></a></div></div>'''


class SuancesTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        current, draft = parse_planning(PLANS)
        self.assertTrue(current['vigente'])
        self.assertFalse(draft['vigente'])
        self.assertEqual(len(current['documentos']), 1)
        self.assertEqual(len(draft['documentos']), 4)
        self.assertEqual(draft['documentos'][2]['role'], 'formulario_alegaciones')
        for row in (current, draft):
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(row[key])
        self.assertEqual(draft['id'], parse_planning(PLANS.replace('random-collapse-123', 'other'))[1]['id'])

    def test_reject_navigation_changed_sections_or_provenance(self):
        for html in ('<nav>PGOU - VIGENTE</nav>', PLANS.replace('no vigente', 'vigente'),
                     PLANS.replace(REGISTER_URL, 'https://example.org/plan')):
            with self.assertRaises(ValueError):
                parse_planning(html)

    def test_no_pagination_truncation(self):
        for parser, html in ((parse_planning, PLANS), (parse_works, page(card()))):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parser(html + '<a rel="next" href="?page=2">2</a>')

    def test_physical_work_and_exclusions(self):
        rows = parse_works(page(card() + card('Solicitud licencia de obras') + card('Anuncio licitación')))
        self.assertEqual(len(rows), 1)
        self.assertIn('redes de abastecimiento', rows[0]['descripcion'])
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://suances.es/wp-content/uploads/calle.jpg')
        self.assertFalse(rows[0]['estado_actual_verificado'])
        with self.assertRaises(ValueError):
            parse_works(page(card('Fiesta municipal')))
        with self.assertRaises(ValueError):
            parse_works(page(card() + card()))

    def test_adapter_writes_complete_snapshot_and_disabled_licences(self):
        def response(url, **kwargs):
            return Mock(url=url, text=PLANS if url == PGOU_URL else page(card()),
                        headers={'Content-Type': 'text/html'})
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.suances.requests.Session') as factory:
            factory.return_value.__enter__.return_value.get.side_effect = response
            adapter = SuancesAyuntamientoAdapter()
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            self.assertEqual(result['source_urls'], [PGOU_URL, WORKS_URL])
            licences = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(licences)['disabled'])
            self.assertEqual(licences.read_text(), '')

    def test_manifest(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/suances/manifest.yaml'
        manifest = load_manifest(path)
        raw = load_yaml(path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Suances', 'Cantabria', '39085'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
