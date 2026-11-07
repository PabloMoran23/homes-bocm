import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cunit import CunitAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest


def inventory(rows='', pagination='disabled'):
    return f'''<div id="content"><div data-pagination='{json.dumps({'type': pagination, 'max_pages': 0})}'>
    <table><thead><tr><th>Títol</th><th>Aprovació inicial</th><th>Estat</th></tr></thead><tbody></tbody></table>
    <table><thead><tr><th>Títol</th><th>Apr. inicial</th><th>Apr. definitiva</th><th>Estat</th></tr></thead><tbody>{rows}</tbody></table></div></div>'''


def row(slug, title='Pla Parcial SUD2', initial='30/07/2019', final='30/04/2020'):
    return f'<tr><td><a href="/planejament/{slug}/">{title}</a></td><td>{initial}</td><td>{final}</td><td>Tancat</td></tr>'


def detail():
    return '''<h1 class="page-header-title">Pla Parcial SUD2</h1><div id="content"><div class="type-planejament">
    <p>Exposició pública: 16 d’agost de 2019</p><p>Publicació BOP 29 juliol 2020</p>
    <a href="/wp-content/uploads/memoria.pdf">Memòria</a><a href="/wp-content/uploads/memoria.pdf">Repetida</a>
    <a href="https://cunit.eadministracio.cat/doc/ABC">Certificat</a></div></div>'''


class CunitTests(unittest.TestCase):
    def test_group_stages_and_document_provenance(self):
        html = inventory(row('aprovacio-definitiva-pla-parcial-sud2-cunit') + row('aprovacio-inicial-pla-parcial-sud-2-pla-de-cunit-2'))
        entries = [(r, Adapter.parse_detail(detail(), r['url'])) for r in Adapter.parse_inventory(html)]
        result = Adapter.group_records(entries)
        self.assertEqual(len(result), 1)
        r = result[0]
        self.assertEqual(r['fecha_aprob'], '2020-04-30')
        self.assertEqual(r['fecha_aprob_inicial'], '2019-07-30')
        self.assertIsNone(r['fecha_publicacion'])
        self.assertIsNone(r['fecha'])
        self.assertEqual(len(r['fuentes']), 2)
        self.assertEqual(len(r['documentos']), 2)
        self.assertEqual(len(r['documentos'][0]['urls_origen']), 2)
        self.assertEqual(r['fuentes'][0]['publicaciones_texto'], ['Publicació BOP 29 juliol 2020'])
        self.assertIsNone(r['lat'])

    def test_closed_is_not_definitive_approval(self):
        r = Adapter.parse_inventory(inventory(row('projecte-actuacio-especifica', final='')))[0]
        record = Adapter.group_records([(r, Adapter.parse_detail(detail(), r['url']))])[0]
        self.assertEqual(record['fase'], 'aprobación inicial')
        self.assertIsNone(record['fecha_aprob_definitiva'])

    def test_reject_pagination_and_changed_sources(self):
        for html in [inventory(row('plan'), 'paged'), inventory(row('plan')).replace('"max_pages": 0', '"max_pages": 2'), '<html>Login</html>', inventory(), inventory(row('plan')).replace('Apr. definitiva', 'Publicació')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory(row('plan')).replace('</div></div>', '<a rel="next" href="?page=2">2</a></div></div>'))

    def test_non_project_and_invalid_dates(self):
        rows = Adapter.parse_inventory(inventory(row('informacio-publica-documentacio-cessio-finca-per-construccio-institut') + row('plan')))
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory(row('plan', initial='31/02/2021')))
        with self.assertRaises(ValueError):
            Adapter.parse_detail('<div id="content">Licence application</div>', SOURCE)
        with self.assertRaises(ValueError):
            Adapter.parse_detail(detail().replace('href=', 'nohref='), SOURCE)

    def test_conflicting_dates_fail(self):
        a = Adapter.parse_inventory(inventory(row('aprovacio-definitiva-pla-parcial-sud2-cunit')))[0]
        b = {**a, 'fecha_aprob_definitiva': '2020-05-01'}
        d = Adapter.parse_detail(detail(), a['url'])
        with self.assertRaises(ValueError):
            Adapter.group_records([(a, d), (b, d)])

    def test_manifest_and_snapshot_update(self):
        manifest = load_manifest('cunit')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(manifest.licencias.enabled)
        adapter = Adapter('cunit')
        with tempfile.TemporaryDirectory() as folder:
            output, state = Path(folder)/'proyectos.jsonl', Path(folder)/'state.json'
            state.write_text('unchanged')
            with patch.object(adapter, '_fetch', side_effect=[inventory(row('plan')), detail()]):
                self.assertEqual(adapter.update_proyectos(output, state)['rows'], 1)
            self.assertEqual(state.read_text(), 'unchanged')
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
