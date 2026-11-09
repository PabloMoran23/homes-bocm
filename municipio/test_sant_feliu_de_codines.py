import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_feliu_de_codines import (
    COMBINED, GRANGES_NORMS, GRANGES_PLAN, SOURCE,
    SantFeliuDeCodinesAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def notice(title=GRANGES_PLAN, day='2023-03-24', action='Aprovació definitiva', doc='955789'):
    return (f'<tr><td><time datetime="{day}"></time></td><td>DOGC</td><td>8882</td>'
            f'<td>{action}<br>{title}</td><td>'
            f'<a href="https://portaldogc.gencat.cat/utilsEADOP/AppJava/PdfProviderServlet?documentId={doc}">PDF</a>'
            f'<a href="https://dogc.gencat.cat/ca/document-del-dogc/?documentId={doc}">Fitxa</a>'
            '<a href="&amp;broken">Bad auxiliary link</a></td><td></td></tr>')


def page(*rows):
    return ('<html><head><title>Planejament urbanístic | Ajuntament de Sant Feliu de Codines | CIDO</title></head>'
            '<body><h2>Planejament urbanístic</h2><table class="adjunts">'
            '<thead><tr><th>Data de publicació</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></body></html>')


class PlanningTests(unittest.TestCase):
    def test_groups_documents_and_distinguishes_dates(self):
        rows = Adapter.parse_projects(page(
            notice(day='2017-04-24', action='Aprovació inicial', doc='1'),
            notice(), notice(),
        ))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_publicacion'], '2023-03-24')
        self.assertEqual(row['fase'], 'Aprovació definitiva')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos'][0]['enlaces']), 2)
        self.assertEqual(row['url'], SOURCE)
        self.assertEqual(row['codigo_ine'], '08210')

    def test_environmental_approval_does_not_approve_plan(self):
        row = Adapter.parse_projects(page(
            notice(day='2017-04-24', action='Aprovació inicial', doc='1'),
            notice(title=GRANGES_PLAN + ', informe ambiental estratègic / Anunci emès pel Departament de Territori',
                   day='2018-05-15', doc='2'),
        ))[0]
        self.assertEqual(row['fase'], 'Aprovació inicial')
        self.assertEqual(row['fecha_publicacion'], '2017-04-24')
        self.assertEqual(row['documentos'][1]['tipo_documento'], 'informe_ambiental')
        with self.assertRaises(ValueError):
            Adapter.parse_projects(page(notice(title=GRANGES_PLAN + ', informe ambiental estratègic')))

    def test_joint_publication_and_reviewed_title_variants(self):
        rows = Adapter.parse_projects(page(
            notice(title=GRANGES_PLAN), notice(title=GRANGES_NORMS, doc='2'),
            notice(title='Normes subsidiàries de planejament del sector Granges', doc='3'),
            notice(title=COMBINED, doc='4'),
        ))
        self.assertEqual(len(rows), 2)
        for row in rows:
            joint = next(d for d in row['documentos'] if d['titulo'] == COMBINED)
            self.assertEqual(joint['relacion'], 'publicacion_conjunta')
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [2, 3])
        a = 'Pla especial urbanístic de desenvolupament per a una activitat ramadera biològica a la carretera de Sant Miquel del Fai'
        self.assertEqual(len(Adapter.parse_projects(page(
            notice(title=a + ' Km 3'),
            notice(title=a + ', km 3, informe ambiental estratègic', doc='9'),
        ))), 1)

    def test_rejects_other_municipality_login_empty_or_pagination(self):
        valid = page(notice())
        for html in [valid.replace('Sant Feliu de Codines', 'Sant Feliu de Llobregat'),
                     '<h1>Login</h1>', page(),
                     valid + '<a rel="next" href="?page=2">Next</a>',
                     valid + '<ul class="pagination"><li>2</li></ul>']:
            with self.subTest(html=html[-80:]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_excludes_non_instruments_and_fails_on_source_changes(self):
        rows = Adapter.parse_projects(page(
            notice(), notice(title='Conveni urbanístic de gestió del carrer Antoni Gaudí'),
            notice(title="Sentència sobre l'aprovació definitiva del Pla parcial urbanístic Les Escoles"),
        ))
        self.assertEqual(len(rows), 1)
        for html in [page(notice(title='Sol·licitud de llicència')),
                     page(notice(day='2023-02-30')),
                     page(notice(action='Acció desconeguda')),
                     page(notice()).replace('https://portaldogc.gencat.cat/', '/').replace('https://dogc.gencat.cat/', '/')]:
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_loads_adapter_and_disables_unsafe_defaults(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/sant-feliu-de-codines/manifest.yaml'
        raw = load_yaml(path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('08210', 'Barcelona'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        self.assertIsInstance(load_portal_adapter(load_manifest(path)), Adapter)

    def test_full_refresh_and_disabled_licences(self):
        adapter = Adapter('sant-feliu-de-codines')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 5}) as backfill:
                self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json'), {'rows': 5})
                backfill.assert_called_once_with(out)


if __name__ == '__main__':
    unittest.main()
