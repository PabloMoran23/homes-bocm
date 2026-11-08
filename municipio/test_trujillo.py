import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.trujillo import TrujilloAyuntamientoAdapter, parse_inventory, parse_detail
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

INVENTORY = """<select id="PtofiguraMunicipio"><option selected value="482">Trujillo</option></select>
<a id="enlacerasterplaneamiento482" onclick="addTab('/SITEX/ptofiguras/viewrefundido/482','Trujillo');"></a>
<a class="unenlaceafiguradeplaneamiento" onclick="addTab('/SITEX/ptofiguras/viewsigcat/40299','Trujillo - NNSS.M-029');">plan</a>"""
DETAIL = """<div id="divplaneamiento40299"><div id="infoplaneamiento40299"><table>
<tr><th>Figura urbanística</th><td>Modificación puntual n.º 27 de las Normas Subsidiarias UE-6.2</td></tr>
<tr><th>Ámbito territorial</th><td>Trujillo</td><td>482</td></tr>
<tr><th>Referencia</th><td>NNSS.M-029</td></tr><tr><th>Estado</th><td>Vigente</td></tr>
<tr><th>Fecha AD</th><td>29/09/2022</td></tr>
<tr><th>Fecha de publicación AD</th><td>29/12/2022</td></tr>
<tr id="filatramite1"><td>29/09/2022</td><td>Acuerdo de la CUOTEX: aprobación definitiva</td></tr>
<tr id="filatramite2"><td>29/12/2022</td><td><a href="http://doe.juntaex.es/plan.pdf">Publicación en DOE</a></td></tr>
</table></div><div id="archivosplaneamiento40299"><table>
<tr><td>Anexo</td><td><a download="Memoria - Anexo" href="/SITEX/ptofiguras/downloaddocumento/11740">PDF</a></td></tr>
<tr><td>Memoria</td><td><a href="/SITEX/ptofiguras/downloaddocumento/11741">PDF</a></td></tr>
</table></div></div>"""


class TrujilloTests(unittest.TestCase):
    def test_inventory_unique_figures_and_scope(self):
        self.assertEqual(list(parse_inventory(INVENTORY + INVENTORY)), ['40299'])
        for value in ('', INVENTORY.replace('Trujillo', 'Trujillanos'),
                      INVENTORY.replace('482', '481'), INVENTORY + '<a rel="next">2</a>',
                      INVENTORY.replace('/viewsigcat/', '/unknown/')):
            with self.assertRaises(ValueError):
                parse_inventory(value)

    def test_instrument_groups_documents_and_dates(self):
        row = parse_detail(DETAIL, '40299')
        self.assertEqual(row['fecha_aprob'], '2022-09-29')
        self.assertEqual(row['fecha_publicacion'], '2022-12-29')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(len(row['tramites']), 2)
        self.assertEqual(row['referencia'], 'NNSS.M-029')
        for field in ('lat', 'lon', 'geometry', 'fecha', 'fecha_acuerdo', 'fase'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_incomplete_or_wrong_detail_rejected(self):
        for value in ('', DETAIL.replace('Trujillo', 'Trujillanos'), DETAIL.replace('Referencia', 'Unknown'),
                      DETAIL.replace('29/09/2022', '31/02/2022')):
            with self.assertRaises(ValueError):
                parse_detail(value, '40299')

    def test_missing_dates_not_inferred_from_procedures(self):
        value = DETAIL.replace('Fecha AD', 'Other').replace('Fecha de publicación AD', 'Other2')
        row = parse_detail(value, '40299')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(len(row['tramites']), 2)

    def test_documents_do_not_leak_between_figures(self):
        value = DETAIL + '<div><a href="/SITEX/ptofiguras/downloaddocumento/99999">Other</a></div>'
        self.assertNotIn('99999', str(parse_detail(value, '40299')['documentos']))

    def test_failure_does_not_write_partial_snapshot(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch('municipio.adapters.trujillo.requests.Session.request', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    TrujilloAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_loads_and_licences_disabled(self):
        manifest = load_manifest('trujillo')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, TrujilloAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
