import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.viladecavalls import SOURCE, ViladecavallsAyuntamientoAdapter, parse_projects
from municipio.manifest import load_manifest, load_yaml


def fixture(extra=''):
    return '''<h1>Planejament vigent</h1><div id="content-core"><div id="parent-fieldname-text">
<h3>Plànol d'Ordenació</h3><p><a href="sector1.pdf">Sector 1</a><a href="sector2.pdf">Sector 2</a></p>
<h3>Documentació escrita</h3><div><ul><li>Normes (Novembre 2008)<a href="normes-urbanistiques.pdf">PDF</a></li>
<li><a href="memoria.pdf">Memòria</a></li></ul>
<h3>Registre</h3><a href="https://example.org">Accedeix</a>
<h3>Projectes d'actuacions específiques i obres i usos provisionals</h3><div><ul>
<li>Projecte d'urbanització del carrer Sabadell: <a href="sabadell.pdf">Memòria</a></li>
<li>Aprovació definitiva dels estatuts i les bases de compensació del Pla Parcial del sector 13: <a href="estatuts.pdf">Estatuts</a> - <a href="bases.pdf">Bases</a></li>
<li><a href="sollicitud.pdf">Sol·licitud per a l'autorització d'ús i obres de caràcter provisional</a></li>
<li><a href="ambit.pdf">Àmbit suspensió potestativa de la unitat VIII</a></li>
<li><a href="avantprojecte.pdf">Avantprojecte Planta Aglomerat Viladecavalls</a></li>
</ul></div></div></div></div>''' + extra


class ParserTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_projects(fixture())
        self.assertEqual(len(rows), 4)
        self.assertEqual([len(r['documentos']) for r in rows], [4, 1, 2, 1])
        self.assertEqual(len({r['id'] for r in rows}), 4)
        self.assertTrue(all(d['source_url'] == SOURCE for r in rows for d in r['documentos']))
        self.assertNotIn('sollicitud', json.dumps(rows))
        self.assertNotIn('ambit.pdf', json.dumps(rows))

    def test_dates_and_geometry_not_inferred(self):
        for r in parse_projects(fixture()):
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(r[key])
            self.assertFalse(r['publication_ready'])
            self.assertEqual(r['codigo_ine'], '08300')
        self.assertIsNone(parse_projects(fixture())[1]['fase'])
        self.assertIn('estatutos', parse_projects(fixture())[2]['fase'])

    def test_changed_source_fails_closed(self):
        for html in ('<h1>Login</h1>', fixture('<a rel="next" href="?page=2">Next</a>'),
                     fixture().replace('normes-urbanistiques.pdf', 'missing.pdf'),
                     fixture().replace('sabadell.pdf', 'https://example.org/sabadell.pdf')):
            with self.subTest(html=html[-90:]), self.assertRaises(ValueError):
                parse_projects(html)

    def test_ids_stable_with_document_label_changes(self):
        first = parse_projects(fixture())
        second = parse_projects(fixture().replace('>Memòria<', '>Document<'))
        self.assertEqual([r['id'] for r in first], [r['id'] for r in second])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('viladecavalls')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08300')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'licencias.jsonl'
            with patch('municipio.adapters.viladecavalls.requests.get') as get:
                result = ViladecavallsAyuntamientoAdapter().backfill_licencias(path)
                get.assert_not_called()
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
