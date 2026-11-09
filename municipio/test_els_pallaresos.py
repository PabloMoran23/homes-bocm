import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from municipio.adapters.els_pallaresos import (
    ElsPallaresosAyuntamientoAdapter, INVENTORY, PARTICIPA, PAGE,
    parse_inventory, parse_notice, parse_documents,
)

PDF = 'https://portaldogc.gencat.cat/utilsEADOP/AppJava/PdfProviderServlet?documentId=1055361&type=01&language=ca_ES'
ROW = f'''<tr><td><time datetime="2026-09-29">29/09/2026</time></td>
<td>Aprovació inicial<br>Avanç del Pla d'Ordenació Urbanística Municipal</td>
<td><a href="{PDF}">PDF</a></td></tr>'''
HTML = '<h1>Ajuntament dels Pallaresos — Planejament urbanístic</h1><table>' + ROW + '</table>'
TEXT = '''Núm. 9760 - 29.9.2026 AJUNTAMENT DELS PALLARESOS
Anunci sobre informació pública de l'avanç del Pla d'ordenació urbanística municipal (exp. 93/2026)
El Ple de l'Ajuntament dels Pallaresos, en sessió ordinària celebrada el dia 11 de juliol de 2026,
va adoptar, entre d'altres, l'acord d'aprovar l'Avanç del Pla d'Ordenació Urbanística Municipal
Els Pallaresos, 15 de setembre de 2026'''
DOCS = '''<section id="poum-documents"><p>POUM dels Pallaresos</p>
<a class="doc-card" href="/wp-content/uploads/programa.pdf"><div class="doc-title">Programa</div></a>
<a class="doc-card" href="/wp-content/uploads/informe.pdf"><div class="doc-title">Informe</div></a>
<div class="doc-card disabled">Avanç — Pròximament</div></section>'''


def payload(content=DOCS):
    return {'id': 1389, 'link': PAGE, 'content': {'rendered': '<script>shadow.innerHTML = `' + content + '`;</script>'}}


class PallaresosTests(unittest.TestCase):
    def test_distinct_agreement_publication_signature(self):
        r = parse_notice(TEXT, '2026-09-29')
        self.assertEqual(r['expediente'], '93/2026')
        self.assertEqual(r['fecha_acuerdo'], '2026-07-11')
        self.assertEqual(r['fecha_publicacion'], '2026-09-29')
        with self.assertRaises(ValueError):
            parse_notice(TEXT, '2026-09-28')
        with self.assertRaises(ValueError):
            parse_notice(TEXT.replace('acord d’aprovar', 'sol·licitud').replace("acord d'aprovar", 'sol·licitud'), '2026-09-29')

    def test_inventory_scope_duplicates_and_pagination(self):
        self.assertEqual(len(parse_inventory(HTML.replace('</table>', ROW + '</table>'))), 1)
        for extra in ['<a rel="next" href="?page=2">2</a>', '<a href="?page=2">Següent</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(HTML + extra)
        for bad in [HTML.replace('Avanç del Pla', 'Formulari del Pla'),
                    HTML.replace('Ajuntament dels Pallaresos', 'Ajuntament de Tarragona'),
                    HTML.replace(PDF, '/formulari.pdf')]:
            with self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_shadow_document_group_and_provenance(self):
        docs = parse_documents(payload())
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(d['source_url'] == PAGE for d in docs))
        self.assertEqual(docs[0]['url'], 'https://elspallaresos.cat/wp-content/uploads/programa.pdf')
        with self.assertRaises(ValueError):
            parse_documents(payload(DOCS.replace('/wp-content/uploads/programa.pdf', 'https://example.com/form.pdf')))
        with self.assertRaises(ValueError):
            parse_documents(payload('<p>Login</p>'))

    def test_snapshot_groups_documents_and_update_refreshes(self):
        adapter = ElsPallaresosAyuntamientoAdapter('els-pallaresos')
        responses = {INVENTORY: HTML.encode(), PARTICIPA: json.dumps(payload()).encode(), PDF: b'%PDF-fake'}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda u, n: responses[u]), patch(
                'municipio.adapters.els_pallaresos.subprocess.run', return_value=SimpleNamespace(stdout=TEXT.encode())):
            path = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 1)
            first = path.read_text()
            r = json.loads(first)
            self.assertEqual(len(r['documentos']), 3)
            self.assertIsNone(r['fecha'])
            self.assertIsNone(r['geometry'])
            self.assertFalse(r['publication_ready'])
            adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(first, path.read_text())
            responses[PDF] = b'<html>Login</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(first, path.read_text())


if __name__ == '__main__':
    unittest.main()
