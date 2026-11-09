"""Offline parser and contract tests, with source-shaped municipal markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_joan_de_labritja import (
    SOURCE, SantJoanDeLabritjaAyuntamientoAdapter, parse_boib, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

INVENTORY = '''<h1>NORMAS SUBSIDIARIAS SANT JOAN DE LABRITJA</h1>
<div data-href="/documentos/NNSS/NNSS_BOIB.pdf">BOIB acuerdo</div>
<a href="/documentos/NNSS/NNSS_BOIB.pdf"></a>
<div data-href="/documentos/NNSS/NNSS-S-Joan-Memoria-AP.pdf">Memoria</div>
<div data-href="/documentos/NNSS/APR-02.TIF">APR-02</div>
<div data-href="/documentos/NNSS/Annex_VI _Memoria.pdf">Anexo VI</div>
<div data-href="/documentos/NNSS/ORDENANZA_PROTECCION_CONJ_HISTORICOS_ACUERDO_CIOTUPHA.pdf">Ordenanza</div>
<div data-href="/documentos/NNSS/CERTIFICADO DE ACUERDO DE LA CMPU 26-09-22.pdf">Instrucción</div>
<a href="/index.php/es/solicitud-de-aprobacion-de-planeamiento">Solicitud</a>
<div data-href="//santjoandelabritja.com/documentos/NNSS/modificacion_puntual_boib/BOIB_aprobacion_mod5.pdf">BOIB APROBACIÓN</div>
<div data-href="/documentos/PTI/MODIFICACIÓN Nº 7 PARCELA CA-1 Y EL-PR EN S.JOAN.pdf">MODIFICACIÓN Nº 7</div>'''
BASE = '''BOIB Num. 104 07-07-2011
Acuerdo de la Comisión Insular de Ordenación del Territorio,
Urbanismo y Patrimonio Historicoartístico de 29 de abril de
2011 de aprobación definitiva de la revisión del planeamiento
general del municipio de Sant Joan de Labritja mediante
Normes Subsidiàries de planejament (PL- 01/2010).
En fecha 21 de diciembre de 2007 se aprobó provisionalmente.'''
MOD5 = '''Núm. 54 24 de abril de 2021
Acuerdo de la Comisión Insular de Ordenación del Territorio, Urbanismo y Patrimonio
Historicoartístico del Consejo Insular de Eivissa, de 12 de abril de 2021, de aprobación definitiva de
la Modificación puntual número 5 de las Normas subsidiarias de Sant Joan de Labritja.
Trámite de aprobación definitiva. Exp. 2020 / 10915Y'''
MOD7 = '''Núm. 89 9 de juliol de 2022
Acord de la Comissió Insular d’Ordenació del Territori, Urbanisme i Patrimoni Historicoartístic del
Consell Insular d’Eivissa, de 6 de juliol de 2022, d’aprovació definitiva de la Modificació puntual
núm. 7 de les Normes Subsidiàries de planejament urbanístic de Sant Joan de Labritja, relativa a
l’ordenació d’una parcel·la. Expedient 2021/15083F'''


class InventoryTests(unittest.TestCase):
    def test_groups_slider_links_and_deduplicates_documents(self):
        groups = parse_inventory(INVENTORY)
        self.assertEqual(set(groups), {'nnss', 'nnss-modificacion-5', 'nnss-modificacion-7'})
        self.assertEqual(len(groups['nnss']['documentos']), 4)
        docs = list(groups['nnss']['documentos'].values())
        self.assertTrue(any(d['url'].endswith('APR-02.TIF') for d in docs))
        self.assertTrue(any('%20' in d['url'] for d in docs))
        self.assertEqual(docs[0]['titulo'], 'BOIB acuerdo')
        self.assertTrue(all(d['inventory_url'] == SOURCE for d in docs))

    def test_navigation_forms_and_missing_act_are_rejected(self):
        for html in ['<a>NNSS</a>', '<h1>NORMAS SUBSIDIARIAS</h1><a href="/solicitud">Solicitud</a>',
                     INVENTORY.replace('NNSS_BOIB.pdf', 'plan.pdf')]:
            with self.subTest(html=html[:30]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_truncating(self):
        for extra in ['<a href="?start=20">2</a>', '<a rel="next" href="/more">2</a>',
                      '<div class="pagination"><a href="/page/2">2</a></div>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(INVENTORY + extra)

    def test_external_attachment_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY + '<div data-href="https://other.example/documentos/NNSS/plan.pdf">Plan</div>')


class ActTests(unittest.TestCase):
    def test_distinct_publication_agreement_and_reference(self):
        cases = [(BASE, 'nnss', '2011-04-29', '2011-07-07', 'PL-01/2010'),
                 (MOD5, 'nnss-modificacion-5', '2021-04-12', '2021-04-24', '2020/10915Y'),
                 (MOD7, 'nnss-modificacion-7', '2022-07-06', '2022-07-09', '2021/15083F')]
        for text, key, agreement, publication, reference in cases:
            with self.subTest(key=key):
                row = parse_boib(text, key)
                self.assertEqual(row['fecha_acuerdo'], agreement)
                self.assertEqual(row['fecha_aprob'], agreement)
                self.assertEqual(row['fecha_publicacion'], publication)
                self.assertEqual(row['expediente'], reference)
                self.assertIsNone(row['fecha'])

    def test_mismatched_identity_and_unverified_dates_fail(self):
        for text, key in [(MOD7, 'nnss-modificacion-5'),
                          (MOD5.replace('Sant Joan de Labritja', 'Sant Josep'), 'nnss-modificacion-5'),
                          (MOD5.replace('24 de abril de 2021', ''), 'nnss-modificacion-5'),
                          (MOD5.replace('aprobación definitiva', 'aprobación provisional'), 'nnss-modificacion-5'),
                          (MOD7.replace('2021/15083F', ''), 'nnss-modificacion-7')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_boib(text, key)


class AdapterTests(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = load_manifest('sant-joan-de-labritja')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07050')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), SantJoanDeLabritjaAyuntamientoAdapter)

    def test_failure_keeps_existing_snapshot(self):
        adapter = SantJoanDeLabritjaAyuntamientoAdapter('sant-joan-de-labritja')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', return_value=b'<h1>Login</h1>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')
            self.assertEqual(adapter.update_licencias(path, Path(directory) / 'state')['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
