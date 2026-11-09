"""Parser and snapshot contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.moratalla import (
    INVENTORY_URL, MoratallaAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(names=('Moratalla', 'Otra')):
    rows = ''.join(f'<tr><td><a href="../Embalse-{n}/">Embalse {n}</a></td>'
                   '<td>5</td><td>Defensa</td><td>2002</td><td>Río</td>'
                   '<td>Hormigón</td><td>C.H.Segura</td><td></td></tr>' for n in names)
    return ('<table id="sortTable"><thead><tr><th>Nombre</th><th>Hm3</th><th>Uso</th>'
            '<th>Constr..</th><th>Cauce</th><th>Tipo material</th>'
            '<th>Gestor/Propietario</th><th>Tour 360º</th></tr></thead><tbody>'
            + rows + '</tbody></table>')


def detail(name='Moratalla', municipality='Moratalla', province='Murcia'):
    return f'''<h2 class="title-componentes">Embalse {name}</h2>
    <table class="ficha"><tr><th>Provincia</th><td>{province}</td></tr>
    <tr><th>Término municipal</th><td>{municipality}</td></tr></table>
    <div><h3>Finalidad</h3><p>Laminación de avenidas.</p></div>
    <div><h3>Planos</h3><a href="/planos/{name}.pdf">Planta</a>
    <a href="/planos/{name}-vaso.pdf">Vaso</a>
    <a href="/planos/{name}.pdf">Planta duplicada</a></div>
    <footer><a href="/seguridad.pdf">Certificado ENS</a></footer>'''


class Response:
    def __init__(self, url, html):
        self.url, self.text = url, html
        self.content = html.encode()
        self.headers = {'Content-Type': 'text/html; charset=utf-8'}

    def raise_for_status(self):
        pass


class MoratallaTests(unittest.TestCase):
    def test_manifest_identity_and_safety(self):
        manifest = load_manifest('moratalla')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']),
                         ('Moratalla', 'Murcia', '30028'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_inventory_reads_all_dom_rows_and_deduplicates(self):
        names = tuple(f'Obra{i}' for i in range(65))
        entries = parse_inventory(inventory(names))
        self.assertEqual(len(entries), 65)  # no first-page or arbitrary record cap
        self.assertEqual(len(parse_inventory(inventory(('A', 'A')))), 1)
        self.assertEqual(entries[-1]['construccion_inventario'], '2002')

    def test_fail_on_missing_table_changed_schema_and_pagination(self):
        for html in ['<p>Captcha</p>', inventory(()), inventory().replace('Gestor/Propietario', 'Otro'),
                     inventory() + '<a rel="next" href="?page=2">→</a>',
                     inventory() + '<script>const opts = {serverSide: true};</script>']:
            with self.subTest(html=html[:40]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_nonofficial_detail_link(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('../Embalse-Moratalla/', 'https://example.org/Embalse-X/'))

    def test_one_work_groups_own_documents_and_retains_provenance(self):
        entry = parse_inventory(inventory())[0]
        row = parse_detail(detail(), entry)
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['source_url'] == entry['url'] for d in row['documentos']))
        self.assertFalse(any('seguridad' in d['url'] for d in row['documentos']))
        self.assertEqual(row['descripcion'], 'Laminación de avenidas.')
        self.assertEqual(row['codigo_ine'], '30028')
        self.assertEqual(row['construccion_inventario'], '2002')
        self.assertFalse(row['publication_ready'])
        self.assertFalse(any(k.startswith('fecha') or k in {'lat', 'lon', 'geometry', 'fase'} for k in row))
        other = parse_detail(detail('Otra'), parse_inventory(inventory())[1])
        self.assertNotEqual(row['id'], other['id'])
        self.assertNotEqual(row['documentos'][0]['url'], other['documentos'][0]['url'])

    def test_filter_uses_structured_jurisdiction_not_narrative(self):
        entry = parse_inventory(inventory())[0]
        for table_class in ['fichatres', 'fichados', 'table table-striped']:
            html = '<meta charset="utf-8">' + detail().replace('class="ficha"', f'class="{table_class}"')
            self.assertIsNotNone(parse_detail(html.encode('utf-8'), entry))
        self.assertIsNone(parse_detail(detail(municipality='Calasparra'), entry))
        self.assertIsNone(parse_detail(detail(municipality='Nueva Moratallana'), entry))
        shared = parse_detail(detail(municipality='Moratalla y Hellín', province='Murcia y Albacete'), entry)
        self.assertEqual(shared['situacion_fuente']['municipio'], 'Moratalla y Hellín')
        for html in [detail(province='Otra'), '<p>Moratalla Murcia</p>',
                     detail().replace('<h3>Planos</h3>', '<h3>Otro</h3>'), detail('Incorrecto')]:
            with self.assertRaises(ValueError):
                parse_detail(html, entry)

    def test_live_path_checks_every_detail_and_failure_preserves_output(self):
        def fetch(session, url, **kwargs):
            if url == INVENTORY_URL:
                return Response(url, inventory())
            if 'Embalse-Moratalla' in url:
                return Response(url, detail())
            return Response(url, detail('Otra', municipality='Calasparra'))

        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', new=fetch), patch('time.sleep'):
            path = Path(tmp) / 'proyectos.jsonl'
            adapter = MoratallaAyuntamientoAdapter('moratalla')
            report = adapter.backfill_proyectos(path)
            self.assertEqual(report['count'], 1)
            self.assertEqual(report['details_checked'], 2)
            self.assertEqual(report['excluded_other_municipalities'], 1)
            self.assertEqual(len(report['source_urls']), 3)
            before = path.read_text()
            with patch('municipio.adapters.moratalla.parse_detail', side_effect=ValueError('broken detail')):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(path.read_text(), before)
            self.assertEqual(json.loads(before)['titulo'], 'Embalse Moratalla')
            self.assertFalse((Path(tmp) / 'state.json').exists())

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get') as get:
            path = Path(tmp) / 'licencias.jsonl'
            report = MoratallaAyuntamientoAdapter('moratalla').backfill_licencias(path)
            self.assertTrue(report['disabled'])
            self.assertEqual(path.read_text(), '')
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
