"""Offline parser and traversal tests; no evidence files or network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.turre import (
    SOURCE, TurreAyuntamientoAdapter, group_instruments, instrument_type,
    inventory_state, official_url, parse_notice,
)
from municipio.manifest import load_manifest, load_yaml

APPROVAL = 'D9A42017A7692D1DC125887C00261FEE'
CORRECTION = '007778503F0BD4BCC125891900290D53'
TITLE = ('APROBACIÓN DEFINITIVA PROYECTO DE REPARCELACIÓN UNIDAD G POLÍGONO 1 '
         'SECTOR R-4 CORTIJO GRANDE expediente municipal 2020/409367/003-626/00001')


def url(ident):
    return 'https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=' + ident


def notice(title=TITLE, published='11/07/2022', docs=('proyecto.pdf',)):
    links = ''.join(f'<a title="{name}" href="/Servicios/Tablon/anexos.nsf/ABC/$file/{name}">{name}</a>'
                    f'<a href="/Servicios/Tablon/anexos.nsf/ABC/$file/{name}">[descargar]</a>' for name in docs)
    return (f'<div id="cmsdip-pro-tablon-anuncios"><div id="doc-dipalme-titulo"><h1>{title}</h1></div>'
            '<div id="doc-lectura-cultura"><h2>Ayuntamiento de Turre</h2>'
            f'<p>Territorio - Planeamiento Urbanístico -</p><div>Publicado: <strong>{published}</strong></div>'
            f'<table id="attachments"><tr><td>{links}</td></tr></table></div></div>')


def inventory(collapsed=False, pager=''):
    button = ('<button id="view:panel:0:col__expand:1button">'
              '<img src="/domjava/xsp/theme/common/images/expand.gif"></button>') if collapsed else ''
    return ('<form class="xspForm"><input name="$$viewid" value="public-state">'
            f'<div id="cmsdip-pro-tablon-view">{button}{pager}'
            f'<div class="tablon-container"><span class="titulo"><a href="{url(APPROVAL)}">{TITLE}</a>'
            '</span></div></div></form>').encode()


class TurreParserTests(unittest.TestCase):
    def test_manifest_identity_and_safety_flags(self):
        manifest = load_manifest('turre')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Turre', 'Almería', '04093'))
        for path in ('licencias', 'schedule'):
            self.assertIs(raw[path]['enabled'], False)
        self.assertIs(raw['geocode']['jitter_missing'], False)

    def test_publication_is_not_approval_date(self):
        record = group_instruments([parse_notice(notice(), url(APPROVAL))])[0]
        self.assertEqual(record['fecha_publicacion'], '2022-07-11')
        self.assertIsNone(record['fecha_acuerdo'])
        self.assertIsNone(record['fecha_aprob'])
        self.assertIsNone(record['geometry'])
        self.assertFalse(record['publication_ready'])
        self.assertEqual(len(record['documentos']), 1)

    def test_correction_and_approval_group_with_all_document_provenance(self):
        original = parse_notice(notice(), url(APPROVAL))
        corrected = parse_notice(notice('RECTIFICACIÓN ERROR MATERIAL ' + TITLE, '15/12/2022',
                                        ('certificado.pdf', 'anexo.pdf')), url(CORRECTION))
        records = group_instruments([corrected, original, original])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['titulo'], TITLE)
        self.assertEqual(len(records[0]['publicaciones']), 2)
        self.assertEqual(len(records[0]['documentos']), 3)
        self.assertEqual(records[0]['documentos'][2]['source_url'], url(CORRECTION))
        self.assertEqual(records[0]['id'], group_instruments([original, corrected])[0]['id'])

    def test_verified_raiu_pair_groups_but_not_same_sector_innovation(self):
        first = parse_notice(notice('Inscripción Registro Autonómico Modificación Plan Parcial Sector R-2 de Turre.'),
                             url('DD74FA168760928FC12583B400279658'))
        second = parse_notice(notice('CORRECCIÓN DE ERRORES. MODIFICACIÓN PUNTUAL DEL PLAN PARCIAL SECTOR R-2.'),
                              url('90513C74461DBAC2C125844F00248B30'))
        innovation = parse_notice(notice('APROBACIÓN DEFINITIVA DE LA INNOVACIÓN Nº 11 DEL P.G.O.U. DE TURRE SECTOR R-2'),
                                  url('9DF4956FED90DE84C12588460039021C'))
        self.assertEqual(len(group_instruments([first, second, innovation])), 2)

    def test_different_expedientes_stay_separate(self):
        a = parse_notice(notice(), url(APPROVAL))
        b = parse_notice(notice(TITLE.replace('/00001', '/00002')), url(CORRECTION))
        self.assertEqual(len(group_instruments([a, b])), 2)

    def test_non_projects_excluded(self):
        for title in ['Modelo solicitud licencia de obras', 'Licitación proyecto de urbanización de la plaza',
                      'APROBACIÓN ESCRITURA JUNTA DE COMPENSACIÓN UE 1 DEL SECTOR I1',
                      'APROBACIÓN BASES Y ESTATUTOS UNIDAD DE EJECUCIÓN 1 DEL PGOU',
                      'Fiestas patronales', 'Concesión de licencia proyecto de actuación']:
            with self.subTest(title=title):
                self.assertIsNone(instrument_type(title))
        self.assertIsNotNone(instrument_type('APROBACIÓN DEFINITIVA DEL PROYECTO DE ACTUACIÓN REFUGIO PÚBLICO EN LOS MORALICOS'))

    def test_changed_markup_missing_documents_and_foreign_notice_fail(self):
        for html in ['<h1>PGOU</h1>', notice(docs=()), notice().replace('Ayuntamiento de Turre', 'Ayuntamiento de Otro'),
                     notice().replace('Publicado:', 'Modificado:'), notice(published='32/13/2022')]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_notice(html, url(APPROVAL))
        with self.assertRaises(ValueError):
            group_instruments([])

    def test_pagination_and_missing_inventory_fail_explicitly(self):
        for html in [b'<html>Maintenance</html>', inventory(pager='<span class="xspPager"><a>2</a></span>'),
                     inventory(pager='<div class="xspDataTableViewPanelFooterMiddle"><button>Next</button></div>')]:
            with self.assertRaises(ValueError):
                inventory_state(html)

    def test_anonymous_category_expansion(self):
        adapter = TurreAyuntamientoAdapter()
        with patch.object(adapter, '_request', side_effect=[inventory(True), inventory()]) as request:
            records = adapter._inventory(object())
        self.assertEqual(list(records), [APPROVAL])
        self.assertEqual(request.call_args.kwargs['data']['$$xspsubmitid'], 'view:panel:0:col__expand:1')
        self.assertEqual(request.call_args.args[1], SOURCE)

    def test_nonprogressing_categories_fail(self):
        adapter = TurreAyuntamientoAdapter()
        with patch.object(adapter, '_request', return_value=inventory(True)), self.assertRaises(ValueError):
            adapter._inventory(object())

    def test_offsite_urls_rejected_and_spaces_encoded(self):
        with self.assertRaises(ValueError):
            official_url('https://example.org/fake.pdf')
        self.assertIn('plan%20parcial.pdf', official_url('/Servicios/Tablon/a/$file/plan parcial.pdf'))

    def test_failed_live_parse_preserves_existing_output(self):
        adapter = TurreAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with patch.object(adapter, '_inventory', return_value={APPROVAL: (url(APPROVAL), TITLE)}), \
                    patch.object(adapter, '_request', return_value=b'<html>broken</html>'), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
