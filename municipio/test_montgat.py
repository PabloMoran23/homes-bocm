"""Parser regressions using reduced excerpts of Montgat's official markup."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.montgat import (
    PLANNING, MontgatAyuntamientoAdapter, enrich,
    parse_detail, parse_inventory, parse_planning_index,
)
from municipio.manifest import load_manifest

TITLE = "Aprovació inicial Modificació puntual del Pla General Metropolità a l'àmbit de les Mallorquines"
LIST = '<div class="journal-content-article"><p>' + TITLE + "</p><p>Projecte nova urbanització carrer Joaquim Costa</p></div>"
URL = PLANNING + '/aprovacio-inicial-mallorquines'
NARRATIVE = ("En sessió celebrada el data 18 de desembre de 2025, el Ple de l'Ajuntament de Montgat "
             "va acordar l'aprovació inicial de la Modificació puntual del Pla General Metropolità "
             "en l'àmbit de Les Mallorquines. Posteriorment, en data 29 de gener de 2026, "
             "va acordar sotmetre-la novament a informació pública (exp. 2248-7868/2025).")
DETAIL = ("<div id='readspeakerPage'><h1>Aprovació inicial de la Modificació del Pla general metropolità "
          "en l'àmbit del barri de les Mallorquines</h1><div class='dinamic'><div class='ddbbtext'><p>" + NARRATIVE + "</p>"
          "<p>Termini d'informació pública: Finalitzat del 16 d'abril de 2026.</p>"
          "<a href='https://tramits.montgat.cat/Ciutadania/ValidarDocuments.aspx?csv=81f60789-f267-4db8-9789-ad0f94c8e57f'>D1. COMPRENSIÓ</a>"
          "</div></div><span class='updated'>Darrera actualització: 2.06.2026 | 13:21</span></div>"
          "<section id='page-documents'><a href='/media/repository/BOPB_08.01.26.pdf'>Anunci BOPB 08.01.26 (133.86KB)</a></section>")
ADVANCE = ("<div id='readspeakerPage'><h1>Avanç de planejament d'un sector del barri de les Mallorquines</h1>"
           "<div class='dinamic'><div class='ddbbtext'><p>A la sessió celebrada el passat 19 d'octubre, "
           "la Corporació va aprovar l'avanç de planejament.</p></div></div></div>"
           "<section id='page-documents'><a href='/media/repository/agenda/Document_de_mobilitat.pdf'>Document de mobilitat</a></section>")


class MontgatTests(unittest.TestCase):
    def test_complete_inventory_unknown_dates_and_no_coordinates(self):
        rows = parse_inventory('<div class=visualitzaciopagina><a href=/home>Home</a>' + LIST + '</div>')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['tipo'], 'obra pública')
        for row in rows:
            for key in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
        self.assertEqual(rows[0]['id'], parse_inventory(LIST)[0]['id'])

    def test_date_semantics_and_grouped_documents(self):
        initial = parse_detail(DETAIL, URL)
        advance = parse_detail(ADVANCE, PLANNING + '/avanc-mallorquines')
        self.assertNotIn('fecha_aprob', advance)  # No inferred year.
        rows = enrich(parse_inventory(LIST), [initial, advance])
        row = rows[0]
        self.assertEqual(row['fecha_aprob'], '2025-12-18')
        self.assertEqual(row['eventos'][1]['fecha_acuerdo'], '2026-01-29')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][1]['fecha_publicacion'], '2026-01-08')
        self.assertEqual(row['documentos'][0]['source_url'], URL)
        self.assertIn('csv=81f60789', row['documentos'][0]['url'])
        self.assertEqual(len(rows), 2)  # Documents and stages are not extra projects.

    def test_index_deduplicates_responsive_menu(self):
        link = "<ul class='widgetMenu'><li><a href='" + URL + "'>Mallorquines</a></li></ul>"
        index = "<div id='readspeakerPage'><h1>Planejament urbanístic</h1>" + link * 2 + '</div>'
        self.assertEqual(list(parse_planning_index(index)), [URL])

    def test_pagination_and_changed_sources_fail(self):
        for page in (LIST + '<a rel="next" href="?page=2">2</a>',
                     LIST + '<div class="pagination"><a href="?page=2">2</a></div>',
                     LIST.replace('Projecte nova urbanització carrer Joaquim Costa', 'Sol·licitud de llicència'),
                     '<html>Sign in</html>'):
            with self.assertRaises(ValueError):
                parse_inventory(page)
        with self.assertRaises(ValueError):
            parse_detail(DETAIL.replace(NARRATIVE, 'Documentació disponible'), URL)
        with self.assertRaises(ValueError):
            parse_detail(DETAIL.replace('Mallorquines', 'Pedreres'), URL)
        with self.assertRaises(ValueError):
            enrich(parse_inventory(LIST), [parse_detail(ADVANCE, URL)])

    def test_live_failure_preserves_existing_output(self):
        adapter = MontgatAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'projects.jsonl'
            output.write_text('previous successful snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=ValueError('source unavailable')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous successful snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('montgat')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.config['ine_code'], '08126')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = MontgatAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
