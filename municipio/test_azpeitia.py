import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.azpeitia import AzpeitiaAyuntamientoAdapter, SOURCE, parse_inventory


def inventory(first, second=''):
    def section(name, body):
        return f'<div class="accordion-item"><div class="accordion-header"><button>{name}</button></div><div class="accordion-body"><ul>{body}</ul></div></div>'
    return '<main id="content">' + section('Garapen planteamendua', first) + section('Plangintza kudeaketa', second) + '</main>'


def entry(title, files=('one.pdf', 'two.pdf')):
    links = ''.join(f'<li><a href="{name if name.startswith("https://") else SOURCE + "/" + name}">{name}</a></li>' for name in files)
    return f'<li>{title}<ul>{links}</ul></li>'


class AzpeitiaParserTests(unittest.TestCase):
    def test_grouping_and_provenance_without_fabricated_dates(self):
        title = 'Trukutxo urbanizazio proiektua (2025PLAN0018)'
        rows = parse_inventory(inventory(entry(title), entry(title, ('two.pdf', 'three.pdf'))))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['expediente'], '2025PLAN0018')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(len(row['source_sections']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon'):
            self.assertIsNone(row[key])

    def test_excludes_agreements_forms_and_unnumbered_legacy(self):
        good = entry('Xehetasun Azterlanaren behin betiko onespena (2026PLAN0001)')
        excluded = ''.join(entry(t) for t in ('Hirigintza hitzarmena (2025PLAN0023)', 'Lizentzia eskaera (2025PLAN0024)', 'Plan berezia'))
        rows = parse_inventory(inventory(good + excluded))
        self.assertEqual([r['expediente'] for r in rows], ['2026PLAN0001'])
        self.assertEqual(rows[0]['fase'], 'aprobación definitiva')

    def test_fail_closed_on_pagination_documents_and_changed_markup(self):
        good = inventory(entry('Plan berezia (2024PLAN0010)'))
        for suffix in ('<a rel="next" href="?page=2">2</a>', '<a href="?b_start:int=20" rel="next">More</a>', '<a href="?start=20">2</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(good + suffix)
        for html in ('<html>Login</html>', inventory(''), inventory(entry('Plan berezia (2024PLAN0010)', ('https://elsewhere.invalid/a.pdf',)))):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_failed_refresh_preserves_previous_output_and_licences_disabled(self):
        adapter = AzpeitiaAyuntamientoAdapter('azpeitia')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with patch('municipio.adapters.azpeitia.requests.get', side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):
                    adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), 'previous snapshot')
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
