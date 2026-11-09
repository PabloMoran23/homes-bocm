import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_pol_de_mar import (
    BASE, SOURCE, SECTIONS, SantPolDeMarAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest
from municipio.entity_policy import classify


def inventory(extra='', section_titles=SECTIONS):
    entries = [
        '<a href="ARXIUS/2026/bus.pdf">Memòria valorada parada N-II, PK 664</a>',
        '<a href="ARXIUS/2026/light.pdf">Projecte enllumenat públic</a>',
        '<a href="ARXIUS/2025/add.pdf">Memòria valorada asfaltatge (addenda)</a>'
        '<a href="ARXIUS/2025/main.pdf">Memòria valorada asfaltatge</a>'
        '<a href="ARXIUS/2025/park.pdf"></a>',
        '<a href="ARXIUS/2025/park.pdf">Projecte baixa tensió Parc del Litoral</a>'
        '<a href="institutescola">Projecte d\'ampliació de l\'escola Sant Pau per a la seva conversió en institut escola</a>'
        '<a href="ARXIUS/school.pdf">Projecte executiu d\'ampliació de l\'escola Sant Pau per a reconversió en institut escola</a>'
        '<a href="ARXIUS/old.pdf">Projecte d\'amplicació de l\'escola Sant Pau</a>',
    ]
    return '<div class="cos_fitxa">' + ''.join(
        '<h2>' + h + '</h2><ul><li>' + e + '</li></ul>'
        for h, e in zip(section_titles, entries)) + extra + '</div>'


class SantPolTests(unittest.TestCase):
    def test_grouping_provenance_and_no_invented_dates(self):
        rows = Adapter.parse_projects(inventory())
        self.assertEqual(len(rows), 5)
        asphalt = next(r for r in rows if 'asfaltatge' in r['titulo'])
        self.assertEqual(len(asphalt['documentos']), 2)
        self.assertEqual(asphalt['url_documento'], BASE + 'ARXIUS/2025/main.pdf')
        school = next(r for r in rows if 'escola Sant Pau' in r['titulo'])
        self.assertEqual(len(school['documentos']), 3)
        park = next(r for r in rows if 'Parc del Litoral' in r['titulo'])
        self.assertEqual(park['fase'], 'Projectes executats')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '08235')
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
            self.assertEqual(classify(row)['entity_type'], 'documento')
            self.assertFalse(classify(row)['activity_eligible'])

    def test_identity_survives_addendum_order(self):
        a = Adapter.parse_projects(inventory())
        b = Adapter.parse_projects(inventory().replace(
            '<a href="ARXIUS/2025/add.pdf">Memòria valorada asfaltatge (addenda)</a>', ''))
        self.assertEqual([r['id'] for r in a], [r['id'] for r in b])

    def test_no_navigation_or_changed_sections(self):
        for html in ('<a href="x.pdf">Projecte</a>', inventory(section_titles=SECTIONS[:-1]),
                     inventory().replace('Projectes executats', 'Projectes nous'),
                     inventory().replace('Projecte enllumenat públic', 'Anunci de licitació')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_never_truncated(self):
        for link in ('<a href="?page=2" rel="next">2</a>',
                     '<a href="?page=2">Següent</a>',
                     '<div class="pagination"><a href="?page=2">2</a></div>'):
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, 'paginated'):
                Adapter.parse_projects(inventory(link))

    def test_bad_or_ambiguous_documents(self):
        for html in (inventory().replace('ARXIUS/2026/bus.pdf', 'https://example.org/bus.pdf'),
                     inventory().replace('ARXIUS/2026/bus.pdf', 'ARXIUS/2026/light.pdf'),
                     inventory('<a href="ARXIUS/unknown.pdf"></a>')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_and_live_method_without_network(self):
        manifest = load_manifest('sant-pol-de-mar')
        self.assertEqual((manifest.nombre, manifest.provincia), ('Sant Pol de Mar', 'Barcelona'))
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            with patch('municipio.adapters.sant_pol_de_mar.requests.get') as get:
                response = get.return_value.__enter__.return_value
                response.url = SOURCE
                response.encoding = 'iso-8859-1'
                response.iter_content.return_value = [inventory().encode('iso-8859-1')]
                result = Adapter('sant-pol-de-mar').update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 5)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 5)
            self.assertEqual(Adapter('sant-pol-de-mar').backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
