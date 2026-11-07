"""Offline parser and adapter tests; run with python -m unittest municipio.test_bermeo."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.bermeo import BermeoAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def fixture():
    root = 'fileadmin/bermeokoudala/doc_bermeo/datu_orokorrak/'
    links = [
        ('II-552_eus.pdf', '-2025-02-07: 26. zk. BAO iragarkia'),
        ('21Memoria_plan_orokorra_eusk.pdf', 'Memoria'),
        ('813.html', 'Planoak'),
        ('II-1623_eus.pdf', '108 zk. BAO iragarkia-II. atala'),
        ('4-_iragarkia.pdf', 'Iragarkia: 21.2 areako 6 eta 9 partzelen Hiri Antolamendurako Plan Berezia.'),
        ('EGIKARITZE_LABURPENA.pdf', '6.1.2 Esku-hartze Areako Hiri Antolamendurako Plan Berezia'),
        ('II-991_eus.pdf', 'Bermeoko HAPOaren katalogoaren aldaketaren behin betiko onarpena. BAO iragarkia 2022-03-21'),
        ('U-HASIERAKO_ONARPENAREN_AKORDIOA.pdf', 'Hasierako onarpenaren akordioa'),
        ('04-23PLAN_BEREZIA.pdf', 'Plan berezia'),
        ('II-5559_eus.pdf', '6.1.2 Esku-hartze Areako Hiri Antolamendurako Plan Bereziaren behin betiko onarpena'),
        ('II-3866_eus.pdf', 'Bermeoko transformazio azpiestazioa eraldatzeko Plan Berezia hasieraz onartzea.'),
    ]
    anchors = ''.join(f'<a href="{name if name.endswith(".html") else root + name}">{label}</a>' for name, label in links)
    return ('<a href="irrelevant.pdf">Licence application</a><div id="seccioncontenido">'
            '<strong>ALDE ZAHARREKO PLAN BEREZIAREN BERRIKUSTAPENA. HASIERAKO ONESPENA</strong>'
            '<strong>BEHIN BETIKOAK</strong><li>Olalde etxearen ingurua berroneratzeko Hiri berrikuntzarako plan berezia<ul></ul></li>'
            '<li>21.2, 8 eta 11 partzelen plan berezia.<ul></ul></li>' + anchors + '</div>')


class BermeoTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = BermeoAyuntamientoAdapter.parse_inventory(fixture())
        self.assertEqual(len(rows), 8)
        by_id = {r['id'].removeprefix('bermeo-proy-'): r for r in rows}
        self.assertEqual(len(by_id['area-6-1-2']['documentos']), 2)
        self.assertEqual(len(by_id['area-21-2-parcelas-8-11']['documentos']), 1)
        self.assertEqual(by_id['area-6-1-2']['fase'], 'aprobación definitiva')
        self.assertIsNone(by_id['area-21-2-parcelas-6-9']['fase'])
        self.assertEqual(by_id['casco-antiguo']['fecha_publicacion'], '2025-02-07')
        self.assertEqual(by_id['catalogo-pgou']['fecha_publicacion'], '2022-03-21')
        self.assertIsNone(by_id['pgou']['fecha_publicacion'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '48017')
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))

    def test_duplicate_and_new_family_document(self):
        extra = '<a href="fileadmin/bermeokoudala/doc_bermeo/beruala/2025_PLAN_BEREZIA/new-map.pdf">Map</a>'
        html = fixture().replace('</div>', extra + extra + '</div>')
        rows = BermeoAyuntamientoAdapter.parse_inventory(html)
        old = next(r for r in rows if r['id'].endswith('casco-antiguo'))
        self.assertEqual(len(old['documentos']), 2)

    def test_pagination_rejected(self):
        for extra in ('<a rel="next" href="?page=2">2</a>',
                      '<a href="?page=2">Hurrengoa</a>', '<div class="pagination">2</div>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                BermeoAyuntamientoAdapter.parse_inventory(fixture().replace('</div>', extra + '</div>'))

    def test_unknown_sources_and_missing_content_rejected(self):
        for html in ('<html>Homepage</html>', fixture().replace('II-3866_eus.pdf', 'new-plan.pdf'),
                     fixture().replace('fileadmin/bermeokoudala/doc_bermeo/datu_orokorrak/II-3866_eus.pdf', 'https://other.example/II-3866_eus.pdf'),
                     fixture().replace('2025-02-07', '2025-02-31')):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                BermeoAyuntamientoAdapter.parse_inventory(html)

    def test_refresh_and_failed_refresh_preserve_output(self):
        response = Mock(content=fixture().encode())
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            adapter = BermeoAyuntamientoAdapter(config={'evidence_dir': directory})
            with patch('municipio.adapters.bermeo.requests.get', return_value=response) as fetch:
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
                self.assertEqual(result['rows'], 8)
                fetch.assert_called_once()
                self.assertEqual(fetch.call_args.args[0], SOURCE)
            before = out.read_bytes()
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 8)
            response.content = b'<html>Homepage</html>'
            with patch('municipio.adapters.bermeo.requests.get', return_value=response), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')
            self.assertEqual((Path(directory) / 'licencias.jsonl').read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('bermeo')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '48017')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.bermeo:BermeoAyuntamientoAdapter')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
