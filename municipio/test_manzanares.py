import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.manzanares import ManzanaresAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def link(title, filename):
    return f'<div><span class="file"><a href="/sites/default/files/docs/urbanismo/{filename}">{title}</a></span></div>'


def inventory(extra=''):
    return ('<div class="view-urbanismo"><div class="view-content"><h3>Plan de Ordenación Municipal</h3>'
            + link('Fichas Urbanísticas', 'fichas.pdf')
            + link('Planos de Ordenación', 'planos.pdf')
            + link('Modificación puntual nº 10', 'mod10.pdf')
            + link('Modificación puntual nº 10', 'mod10_anexo.pdf')
            + link('Modificación puntual nº 11', 'mod11.pdf')
            + link('Normas Urbanísticas del Plan Parcial del PAU del Sector 5 (anuncio del BOP)', 'sector5.pdf')
            + extra + '<h3>Otros</h3>'
            + link('POM cartografía (archivo dwg)', 'pom.dwg')
            + link('Solicitud licencia de obra', 'solicitud.pdf')
            + link('Estudio de viabilidad del contrato de abastecimiento de agua', 'viabilidad.pdf')
            + '</div></div>')


class ManzanaresTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        rows = Adapter.parse_projects(inventory())
        groups = {r['id']: r for r in rows}
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(groups['manzanares-proy-pom']['documentos']), 3)
        self.assertEqual(len(groups['manzanares-proy-pom-mod-10']['documentos']), 2)
        self.assertEqual(len(groups['manzanares-proy-pom-mod-11']['documentos']), 1)
        self.assertEqual(len(groups['manzanares-proy-plan-parcial-sector-5']['documentos']), 1)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '13053')
            self.assertEqual(row['source_entity_type'], 'documento')
            for field in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            for doc in row['documentos']:
                self.assertEqual(doc['url_fuente'], SOURCE)
                self.assertNotIn('solicitud', doc['url'])
                self.assertNotIn('viabilidad', doc['url'])

    def test_duplicate_links(self):
        rows = Adapter.parse_projects(inventory(link('Modificación puntual nº 10', 'mod10.pdf')))
        self.assertEqual(len(rows[1]['documentos']), 2)

    def test_fail_closed(self):
        for html in ('<html>Error</html>', inventory().replace('view-urbanismo', 'changed'),
                     inventory() + '<ul class="pager"><li><a href="?page=1">2</a></li></ul>',
                     inventory() + '<a rel="next" href="?page=1">Más</a>',
                     inventory(link('Nuevo documento sin clasificar', 'nuevo.pdf')),
                     inventory().replace('mod10.pdf', '../../../foreign.txt')):
            with self.subTest(html=html[:100]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_loader_and_snapshot_update(self):
        raw = load_yaml(Path('data/municipios/manzanares/manifest.yaml'))
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('13053', 'Ciudad Real'))
        for section, key in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[section][key], False)
        adapter = load_portal_adapter(load_manifest('manzanares'))
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 4}) as fetch:
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state.json')['rows'], 4)
                fetch.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()
