"""Offline structural fixtures; live evidence is deliberately not a test dependency."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.llica_d_amunt import LlicaDAmuntAyuntamientoAdapter as Adapter
from municipio.adapters.llica_d_amunt import PLANNING, STUDIES
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def link(name, label):
    return f'<a href="/media/repository/{name}.pdf">{label}</a>'


def planning():
    return f'''<main><h1>Planejament urbanístic</h1><div class="ddbbtext">
    <p>Consulteu el planejament urbanístic vigent</p>
    <h2>Pla d'ordenació urbanística municipal (POUM)</h2>
    <h3>Normes urbanístiques</h3><ul><li>{link('normes', 'Normes 2014')}</li></ul>
    <h3>Plànols</h3><ul><li>{link('planol', 'Plànol')}</li></ul>
    <h3>Correcció d'errades materials al Pla d'ordenació urbanística municipal de Lliçà d'Amunt</h3>
    <ul><li>Correcció de fitxa {link('correccio', 'VEURE DOGC')}</li></ul>
    <h3>Modificacions del Pla d'ordenació urbanística municipal</h3>
    <ul><li>Modificació del POUM Can Malé {link('mod', 'VEURE DOGC')}</li></ul>
    <h3>Suspensió de llicències</h3><ul><li>{link('suspensio', 'Suspensió')}</li></ul>
    <h2>Planejament urbanístic</h2>
    <h3>Planejament aprovat definitivament per l'Ajuntament</h3>
    <ul><li>{link('anunci', 'Anunci BOPB Pla de Millora Urbana PMU-6 Pinsos Tenes')}</li>
    <li>{link('pmu', 'PMU-6 Pinsos del Tenes')}</li></ul>
    <h3>Altre planejament no publicat al Registre</h3>
    <ul><li>{link('especial', 'Pla Especial del veïnat de Can Ballestà')}</li>
    <li>{link('especial_mod', 'Modificació del Pla Especial del veïnat rural de Can Ballestà')}</li></ul>
    </div><span>Darrera actualització: 10.07.2026</span></main>'''


def studies(count=1):
    headers = ['Expedient', 'Emplaçament', 'Qualificació urbanística', 'Clau',
               'Documentació escrita', 'Documentació gràfica', 'Documentació administrativa']
    rows = []
    for i in range(1, count + 1):
        cells = [f'ED {i}-77', f'Tenes,{i}', 'Zona suburbana', '2a']
        cells += [link(f'ed{i}{suffix}', suffix) for suffix in ('de', 'dg', 'da')]
        rows.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
    return ('<main><h1>Estudis de detall</h1><p>Relació d’estudis de detall vigents</p><table><tr>'
            + ''.join(f'<th>{h}</th>' for h in headers) + '</tr>' + ''.join(rows)
            + '</table><p>Darrera actualització: 10.05.2018</p></main>')


class ParserTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = Adapter.parse_planning(planning())
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(rows[0]['documentos']), 3)
        pmu = next(r for r in rows if 'PMU-6' in r['titulo'])
        self.assertEqual(len(pmu['documentos']), 2)
        self.assertEqual(pmu['fase'], 'aprobación definitiva')
        self.assertEqual(rows[-1]['tipo'], 'modificacion_planeamiento')
        self.assertNotIn('suspensio', json.dumps(rows))
        self.assertNotIn('VEURE DOGC', rows[1]['titulo'])
        for row in rows:
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertEqual(row['codigo_ine'], '08107')
            self.assertFalse(row['publication_ready'])
            for doc in row['documentos']:
                self.assertEqual(doc['url_fuente'], PLANNING)

    def test_studies_group_three_documents_without_row_cap(self):
        rows = Adapter.parse_studies(studies(75))
        self.assertEqual(len(rows), 75)
        self.assertEqual(rows[-1]['expediente'], 'ED 75-77')
        self.assertTrue(all(len(r['documentos']) == 3 for r in rows))
        self.assertEqual(rows[0]['direccion'], 'Tenes,1')
        self.assertIsNone(rows[0]['fecha_aprob'])  # Neither dossier year nor page-update date.

    def test_stable_identity_after_reordering_documents(self):
        html = planning()
        first = link('anunci', 'Anunci BOPB Pla de Millora Urbana PMU-6 Pinsos Tenes')
        second = link('pmu', 'PMU-6 Pinsos del Tenes')
        changed = html.replace(first, 'SWAP').replace(second, first).replace('SWAP', second)
        self.assertEqual([r['id'] for r in Adapter.parse_planning(html)],
                         [r['id'] for r in Adapter.parse_planning(changed)])

    def test_reject_navigation_login_and_unrelated_forms(self):
        for html in ('<main>Login</main>', '<main><h1>Planejament urbanístic</h1><a>POUM</a></main>'):
            with self.assertRaises(ValueError):
                Adapter.parse_planning(html)
        with self.assertRaises(ValueError):
            Adapter.parse_planning(planning().replace('Pla Especial del veïnat de Can Ballestà', 'Sol·licitud de llicència'))

    def test_pagination_and_schema_changes_fail_closed(self):
        for parser, html in ((Adapter.parse_planning, planning()), (Adapter.parse_studies, studies())):
            for markup in ('<a href="?page=2">Següent</a>', '<div class="pagination">2</div>', '<link rel="next" href="?page=2">'):
                with self.assertRaises(ValueError):
                    parser(html.replace('</main>', markup + '</main>'))
        for html in (studies().replace('<th>Clau</th>', '<th>Changed</th>'),
                     studies().replace(link('ed1da', 'da'), ''),
                     studies().replace('ED 1-77', 'No dossier')):
            with self.assertRaises(ValueError):
                Adapter.parse_studies(html)

    def test_manifest_and_atomic_snapshot(self):
        manifest = load_manifest('llica-d-amunt')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08107')
        self.assertEqual(manifest.provincia, 'Barcelona')
        for group, field in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[group][field], False)
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        adapter = Adapter('llica-d-amunt')
        with TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[planning(), '<main>Login</main>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[planning(), studies()]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 6)
            self.assertEqual(len(out.read_text().splitlines()), 6)
            self.assertEqual(result['source_urls'], [PLANNING, STUDIES])
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
