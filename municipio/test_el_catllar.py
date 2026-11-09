import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.el_catllar import ElCatllarAyuntamientoAdapter as Adapter, HEADERS
from municipio.manifest import load_manifest


def row(title="Pla d'Ordenació Urbanística del Catllar", approval='22-04-2009',
        publication='09-02-2010', dossier='242676', extra=''):
    values = [approval, publication, '', '', '', '', title, '',
              f'<a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/{dossier}/documents">RPUC</a>', extra, '']
    return '<tr>' + ''.join(f'<td>{v}</td>' for v in values) + '</tr>'


def page(rows, script=''):
    return ('<title>Planejament urbanístic - Ajuntament del Catllar</title>'
            '<table id="plans"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS)
            + '</tr></thead><tbody>' + rows + '</tbody></table>' + script)


class ElCatllarTests(unittest.TestCase):
    def test_dates_identity_and_source_classification(self):
        record = Adapter.parse_projects(page(row()))[0]
        self.assertEqual(record['fecha_aprob'], '2009-04-22')
        self.assertEqual(record['fecha_publicacion'], '2010-02-09')
        self.assertIsNone(record['fecha_acuerdo'])
        self.assertIsNone(record['fase'])
        self.assertIsNone(record['lat'])
        self.assertEqual(record['codigo_ine'], '43043')
        self.assertFalse(record['publication_ready'])

    def test_missing_dates_and_grouped_documents(self):
        pdf = '<a href="/documents/1121585/projecte.pdf">Memòria</a>'
        records = Adapter.parse_projects(page(row(approval='', publication='') +
                                              row(approval='', publication='', extra=pdf)))
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]['documentos']), 2)
        self.assertIsNone(records[0]['fecha_aprob'])

    def test_malformed_live_row_endings_and_blank_row(self):
        # The source nests rows because </tr> is omitted, including a blank row.
        blank = '<tr>' + '<td></td>' * 11
        html = page(row().replace('</tr>', '') + blank +
                    row(dossier='285254').replace('</tr>', ''))
        records = Adapter.parse_projects(html)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(records[0]['documentos']), 1)

    def test_more_than_one_browser_page_is_not_truncated(self):
        self.assertEqual(len(Adapter.parse_projects(page(''.join(
            row(dossier=str(242676 + i)) for i in range(25))))), 25)

    def test_invalid_sources_fail_closed(self):
        invalid = ['<title>Login</title>', page(''), page(row(title='Sol·licitud de llicència')),
                   page(row(approval='31-02-2020')), page(row(dossier='bad')),
                   page(row()) + '<a rel="next" href="?page=2">Següent</a>',
                   page(row(), '<script>$("#plans").DataTable({serverSide: true});</script>'),
                   page(row(), '<script>$("#plans").DataTable({ajax: "/api"});</script>'),
                   page(row() + row(approval='01-01-2010'))]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_update_refresh_and_disabled_licences(self):
        adapter = Adapter('el-catllar')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 5}) as fetch:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('state')), {'rows': 5})
            fetch.assert_called_once_with(Path('unused'))
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
        manifest = load_manifest('el-catllar')
        self.assertEqual(manifest.provincia, 'Tarragona')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
