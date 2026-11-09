import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.valdovino import SOURCE, ValdovinoAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def fixture(links=None):
    links = links if links is not None else '<a href="/arquivo/sites/default/files/informacion.pdf">Memoria</a><a href="/arquivo/sites/default/files/dog.pdf">Resolución no DOG</a>'
    return '<h1>Delimitación de novos núcleos rurais</h1><div class="wpb_text_column"><div class="wpb_wrapper"><h4>Modificación puntual núm. 14 das NNSSPP para delimitación de solo de núcleo rural:</h4>' + links + '</div></div><aside><a rel="next" href="/news/page/2">Next</a><a href="/licitacion">Licitación</a></aside>'


class ValdovinoTests(unittest.TestCase):
    def test_groups_documents_and_preserves_date_semantics(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '15087')
        for field in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(rows[0][field])
        self.assertFalse(rows[0]['publication_ready'])

    def test_deduplicates_attachments(self):
        link = '<a href="/arquivo/sites/default/files/dog.pdf">DOG</a>'
        self.assertEqual(len(parse_inventory(fixture(link * 2))[0]['documentos']), 1)

    def test_missing_inventory_fails(self):
        for html in ['<h1>Login</h1>', fixture(''), fixture().replace('Modificación puntual', 'Solicitud de licencia')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_inventory_pagination_and_unexpected_documents_fail(self):
        for links in ['<a rel="next" href="?page=2">Seguinte</a>', '<a href="https://example.org/file.pdf">Plano</a>']:
            with self.subTest(links=links), self.assertRaises(ValueError):
                parse_inventory(fixture(links))

    def test_registry_and_live_method_contract(self):
        manifest = load_manifest('valdovino')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE, content=fixture().encode())
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.valdovino.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
            first = output.read_text()
            adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), first)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_fetch_failure_does_not_replace_output(self):
        adapter = ValdovinoAyuntamientoAdapter('valdovino')
        response = Mock(url=SOURCE, content=b'<h1>Login</h1>')
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.valdovino.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
