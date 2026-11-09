"""Offline parser contract tests; no captured website is needed to run these."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.almodovar_del_campo import (
    SOURCE, AlmodovarDelCampoAyuntamientoAdapter, parse_inventory,
)


def fixture():
    links = ''.join(f'<tr><td><a href="/docs/{i}.pdf">{label}</a></td></tr>'
                    for i, label in enumerate(('MEMORIA INFORMATIVA', 'NORMAS URBANÍSTICAS', 'PLANOS ORDENACIÓN', 'MEMORIA ISA')))
    return f'''<article><h1 class="entry-title">Proyecto de POM (Plan de Ordenación Municipal) 2ª Información Pública</h1>
    <div class="entry-content"><p>Ayuntamiento de Almodóvar del Campo. Informe de Sostenibilidad Ambiental.
    Decreto de 14 de septiembre de 2004. El periodo se prolonga a contar desde el 28 de enero de 2022.</p>
    <table><thead><tr><th>Documento PDF disponible</th></tr></thead><tbody>{links}</tbody></table></div></article>'''


class InventoryTests(unittest.TestCase):
    def test_groups_documents_and_preserves_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '13015')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['documentos'][0]['url'], 'https://www.almodovardelcampo.es/docs/0.pdf')
        self.assertTrue(all(d['inventory_url'] == SOURCE for d in row['documentos']))
        self.assertEqual(row['fecha_inicio_informacion_publica'], '2022-01-28')
        for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_rejects_forms_empty_inventory_and_changed_instrument(self):
        for html in ('<p>LICENCIA DE OBRAS: Solicitud e Instrucciones</p>',
                     fixture().replace('Documento PDF disponible', 'Solicitudes'),
                     fixture().replace('NORMAS URBANÍSTICAS', 'Solicitud'),
                     fixture().replace('2ª Información Pública', 'Anuncio de contratación')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_rejects_pagination(self):
        for pagination in ('<a rel="next" href="?page=2">Next</a>',
                           '<div class="page-links"><a href="/2/">2</a></div>'):
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(fixture() + pagination)

    def test_duplicate_links_and_unknown_date(self):
        html = fixture().replace('</tbody>', '<tr><td><a href="/docs/0.pdf">Duplicate</a></td></tr></tbody>')
        self.assertEqual(len(parse_inventory(html)[0]['documentos']), 4)
        row = parse_inventory(fixture().replace('a contar desde el', 'sin fecha explícita'))[0]
        self.assertIsNone(row['fecha_inicio_informacion_publica'])
        self.assertEqual(row['id'], parse_inventory(fixture())[0]['id'])

    def test_licences_disabled_without_network_and_update_refreshes(self):
        adapter = AlmodovarDelCampoAyuntamientoAdapter('almodovar-del-campo')
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            with patch('municipio.adapters.almodovar_del_campo.requests.get') as get:
                self.assertTrue(adapter.backfill_licencias(output)['disabled'])
                self.assertEqual(output.read_text(), '')
                get.assert_not_called()
            with patch.object(adapter, 'backfill_proyectos', return_value={'count': 1}) as backfill:
                self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state.json'), {'count': 1})
                backfill.assert_called_once_with(output)


if __name__ == '__main__':
    unittest.main()
