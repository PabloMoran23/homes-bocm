import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.argentona import ArgentonaAyuntamientoAdapter as Adapter, SOURCES
from municipio.manifest import load_manifest, load_yaml


def page(*links):
    return '<div class="document"><div id="cos">' + ''.join(
        f'<p><a href="ARXIUS/{name}.pdf">{title}</a></p>' for name, title in links
    ) + '</div></div>'


def parse(html, inventory='documentos_aprobados'):
    return Adapter.parse_inventory(html, SOURCES[inventory], inventory)


class ArgentonaTests(unittest.TestCase):
    def test_exclude_administrative_documents_and_forms(self):
        docs = parse(page(
            ('work', "Aprovació inicial de projecte d'urbanització de la UA Can Cabot - Subunitat B"),
            ('finance', 'Projecte de contribucions especials - obres de Madà'),
            ('suspension', 'Suspensió potestativa de projectes urbanístics'),
            ('form', 'Sol·licitud de llicència d’obres'),
            ('plan', "Pla d'emergència en situacions de sequera"),
            ('statutes', 'Estatuts de la Junta de Compensació del PMU-2'),
            ('deed', 'Proforma de reparcel·lació PA9 Ben Plantada'),
        ))
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['fase'], 'aprobación inicial')

    def test_versions_group_but_distinct_instruments_stay_separate(self):
        docs = parse(page(
            ('initial', 'Aprovació inicial del projecte per la reurbanització de la cruïlla d’Avinguda Puig i Cadafalch entre els carrers Dr. Farrero i Mataró'),
            ('final', 'Aprovació definitiva del projecte executiu de reurbanització de la cruïlla av. Puig i Cadafalch entre el carrer Farrero i Carrer Mataró'),
            ('garden', 'Text refós del projecte de rehabilitació del jardí de la Casa Puig i Cadafalch'),
            ('parcel', 'Projecte de reparcel·lació del PA-13 Serra Lladó'),
            ('deed', 'Escriptura de reparcel·lació voluntària del PA-13 Serra Lladó'),
            ('urban', "Aprovació inicial projecte d'urbanització del PA-13 Serra Lladó"),
        ))
        rows = Adapter.group_documents(docs + docs)
        self.assertEqual(len(rows), 4)
        junction = next(r for r in rows if 'cruïlla' in r['titulo'])
        self.assertEqual(len(junction['documentos']), 2)
        self.assertIsNone(junction['fase'])
        self.assertEqual(junction['fases_documentadas'], ['aprobación definitiva', 'aprobación inicial'])

    def test_declared_latin1_charset(self):
        html = '<meta charset="iso-8859-1">' + page(('a', 'Memòria valorada Illeta Can Barrau'))
        self.assertEqual(parse(html.encode('iso-8859-1'))[0]['titulo'], 'Memòria valorada Illeta Can Barrau')

    def test_unknown_dates_and_geometry_filename_not_agreement(self):
        row = Adapter.group_documents(parse(page(('20260108_projecte', 'Projecte rehabilitació del dipòsit del Rocar'))))[0]
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_reject_empty_login_and_pagination(self):
        for html in ('<form>Login</form>', page(('form', 'Formulari de llicència')),
                     page(('work', 'Projecte de construcció')) + '<a rel="next" href="?p=2">2</a>',
                     page(('work', 'Projecte de construcció')) + '<a href="?pagina=2">2</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse(html)

    def test_failure_does_not_overwrite_snapshot(self):
        adapter = Adapter('argentona')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'rows.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[page(('a', 'Projecte de construcció')), '<form>Login</form>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_and_complete_refresh(self):
        manifest = load_manifest('argentona')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08009')
        self.assertEqual(manifest.provincia, 'Barcelona')
        for section, key in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertIs(raw[section][key], False)
        adapter = Adapter('argentona')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=page(('a', 'Projecte de construcció'))):
            output = Path(tmp) / 'rows.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'lic.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
