import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.viana import SOURCE, VianaAyuntamientoAdapter, enrich_detail, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<main><div class="contenido content">' + body + '</div></main>'


INVENTORY = page('''<p><a href="/antifraude/">PLAN ANTIFRAUDE</a></p>
<p>DUS 5000</p><ul>
<li><a href="/alumbrado/">Renovación del alumbrado público</a></li>
<li>Instalación de generación térmica mediante aerotermia para la Casa Consistorial</li>
<li><a href="/colegio/">Reforma de la envolvente térmica del Colegio Público</a></li>
<li><a href="/alumbrado/">Renovación del alumbrado público</a></li></ul>
<a href="/otra-noticia/">Fiestas</a>''')
DETAIL = page('''<h2>DUS5000</h2><p>Ayuda PR-D5000-2021-000177 concedida el 27 de octubre de 2022.</p>
<p>1. Descripción del proyecto: sustitución de luminarias.</p>
<a href="/plan.pdf">Plan Estratégico</a><a href="/plan.pdf">Plan repetido</a>''')


class VianaTests(unittest.TestCase):
    def test_inventory_scope_grouping_and_unknown_dates(self):
        rows = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['url'], SOURCE)
        self.assertFalse(rows[1]['detalle_disponible'])
        enriched = enrich_detail(rows[0], DETAIL)
        self.assertEqual(len(enriched['documentos']), 3)
        self.assertEqual(enriched['expediente_ayuda'], 'PR-D5000-2021-000177')
        self.assertFalse(any(k.startswith('fecha') for k in enriched))
        self.assertNotIn('lat', enriched)
        self.assertEqual(enriched['codigo_ine'], '31251')

    def test_reject_missing_changed_and_paginated_sources(self):
        for html in [page(''), INVENTORY.replace('<ul>', '<ol>'),
                     INVENTORY.replace('Renovación del alumbrado público', 'Solicitud de licencia'),
                     INVENTORY.replace('</main>', '<a rel="next" href="/page/2/">2</a></main>'),
                     INVENTORY.replace('</main>', '<a href="?paged=2">2</a></main>'),
                     INVENTORY.replace('/alumbrado/', 'https://example.org/obra/')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            enrich_detail(parse_inventory(INVENTORY)[0], page('Anuncio de licitación'))

    def test_adapter_manifest_full_refresh_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('viana'))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(VianaAyuntamientoAdapter, '_fetch', side_effect=[INVENTORY, DETAIL, DETAIL]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(out.read_text().splitlines()), 3)
            original = out.read_text()
            with patch.object(VianaAyuntamientoAdapter, '_fetch', side_effect=[INVENTORY, page('broken')]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
