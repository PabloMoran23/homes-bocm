import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cervello import CervelloAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def detail(title, body='', docs=True):
    return (f'<div id="readspeakerPage"><h1>{title}</h1><div class="date"></div>'
            f'<div class="ddbbtext">{body}</div><span class="updated">Darrera actualització: 01.01.2026</span></div>'
            + ('<section id="page-documents"><a href="/media/project.pdf">Memòria</a>'
               '<a href="/media/plans.pdf">Plànols</a></section>' if docs else ''))


def inventory(urls, pages):
    return ('<main id="readspeakerPage"><h1>Obra pública</h1>'
            + ''.join(f'<li class="article-item"><a href="{u}">Projecte</a></li>' for u in urls)
            + '<ul class="paginacio">' + ''.join(f'<a href="{u}">page</a>' for u in pages)
            + f'<a class="info">{len(pages)} pàgines</a></ul></main>')


class CervelloTests(unittest.TestCase):
    def test_dates_and_conditional_approval(self):
        row = Adapter.parse_detail(detail('Aprovació definitiva del Projecte de clavegueram',
            'En sessió ordinària data 12 de maig de 2026, va aprovar inicialment el projecte. '
            'Publicat al BOP de 21 de maig de 2026. Quedant aprovat definitivament.'), SOURCE + '/test.html')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['acuerdos'][0]['fecha_acuerdo'], '2026-05-12')
        self.assertEqual(row['acuerdos'][0]['fase'], 'aprobación inicial')
        row = Adapter.parse_detail(detail('Aprovació inicial del Projecte de clavegueram',
            'En sessió ordinària de data 23 de setembre de 2026, ha acordat el següent: '
            '1r.- Aprovar inicialment el projecte. Si no hi ha reclamacions esdevindrà aprovat definitivament.'), SOURCE + '/test.html')
        self.assertEqual(row['fecha_acuerdo'], '2026-09-23')
        self.assertEqual(row['fase'], 'aprobación inicial')

    def test_group_documents_and_approval_notices(self):
        rows = [Adapter.parse_detail(detail(t), SOURCE + '/' + str(i) + '.html') for i, t in enumerate([
            'Aprovació inicial del “Projecte constructiu de sanejament en baixa de Les Rovires”',
            'Aprovació definitiva del "Projecte constructiu de sanejament en baixa de Les Rovires"'])]
        grouped = Adapter.group_projects(rows)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]['anuncios']), 2)
        self.assertEqual(len(grouped[0]['documentos']), 4)  # each link retains its notice provenance
        self.assertEqual(grouped[0]['fase'], 'aprobación definitiva')
        self.assertEqual(Adapter.group_projects(rows[:1])[0]['id'], grouped[0]['id'])
        self.assertIsNone(grouped[0]['lat'])

    def test_reject_navigation_and_exclude_policy(self):
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<h1>Login</h1>')
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail('Aprovació inicial del Projecte buit', docs=False), SOURCE)
        for title in ['Formulari de llicència', 'Anunci de licitació', 'Notícies',
                      'Aprovació definitiva del Pla de prevenció d’incendis',
                      'Aprovació definitiva del Document únic de protecció civil municipal']:
            self.assertIsNone(Adapter.parse_detail(detail(title), SOURCE))

    def test_pagination_full_snapshot_and_failure_is_atomic(self):
        a, b, p2 = SOURCE + '/a.html', SOURCE + '/b.html', SOURCE + '?pag=2'
        responses = {SOURCE: inventory([a], [SOURCE, p2]), p2: inventory([b], [SOURCE, p2]),
                     a: detail('Aprovació inicial del Projecte A'), b: detail('Aprovació definitiva del Projecte B')}
        adapter = Adapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda u: responses[u]) as fetch:
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['rows'], 2)
            self.assertEqual(fetch.call_count, 4)
            self.assertEqual(len(path.read_text().splitlines()), 2)
            responses[p2] = '<h1>Service unavailable</h1>'
            previous = path.read_bytes()
            with self.assertRaises(ValueError):
                adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_bytes(), previous)
        broken = inventory([a], [SOURCE, p2]).replace('2 pàgines', '3 pàgines')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(broken)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cervello')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08068')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(Adapter().backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
