"""Deterministic parser and pagination regressions; no network in tests."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.benahavis import (
    BASE, SOURCE, BenahavisAyuntamientoAdapter, ajax_components, documents,
    family, folders, group_projects, preview_metadata,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def link(n, title):
    return f'<a class="gIconLink" href="{BASE}/preview-document/00000000-0000-0000-0000-{n:012d}">{title}</a>'


MORE = '''<div class="more_results" id="more"><button onclick="wicketAjaxGet('?x=more',null)">Mostrar más</button></div>'''


def ajax(content, end=False):
    return ('<ajax-response><component id="row"><![CDATA[' + content + ']]></component>'
            + ('<component id="more"><![CDATA[<div id="more" style="display: none"></div>]]></component>' if end else '')
            + '</ajax-response>')


class FakeAdapter(BenahavisAyuntamientoAdapter):
    def __init__(self, responses):
        super().__init__('benahavis')
        self.responses = iter(responses)

    def _get(self, session, url, ajax=False):
        return next(self.responses), None


class BenahavisTests(unittest.TestCase):
    def test_manifest_resolves_and_safety_flags(self):
        m = load_manifest('benahavis')
        raw = load_yaml(m.path)
        self.assertIsInstance(load_portal_adapter(m), BenahavisAyuntamientoAdapter)
        self.assertEqual((m.nombre, m.provincia, raw['codigo_ine']), ('Benahavís', 'Málaga', '29023'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(m.licencias.enabled)

    def test_group_documents_not_sheet_projects(self):
        html = ''.join([link(1, 'PROYECTO URBANIZACION PROINDIVISO A RLQ - 1'),
                        link(2, 'PROYECTO URBANIZACION PROINDIVISO A RLQ - 7'),
                        link(3, '101_MEM_MEMORIA_ESTUDIO DETALLE _EL MADRONAL 3-4 Y 5_F_signed'),
                        link(4, '201_PL_ESTUDIO DETALLE _EL MADRONAL 3-4 Y 5_F_signed'),
                        link(5, 'EDICTO INICIAL MODIFICACION ED MADROÑAL'),
                        link(6, '31-O.E.1.TERMINO'),
                        link(7, 'Solicitud de Licencia o Autorización Urbanística'),
                        link(8, 'ACTA APERTURA PLICAS PPU 17')])
        rows = group_projects(documents(html, SOURCE))
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [2, 3])
        for r in rows:
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(r[key])
            self.assertFalse(r['publication_ready'])
        self.assertEqual(rows[0]['id'], group_projects(list(reversed(documents(html, SOURCE))))[0]['id'])
        self.assertIsNone(family('ZAGALETA_EstudioDeDetalle (Anulado)'))
        self.assertIsNone(family('RIU 2022-0001 [TOMO I] (Anulado)'))

    def test_no_candidate_is_error(self):
        with self.assertRaises(ValueError):
            group_projects(documents(link(1, 'MAPAS-CALLEJERO'), SOURCE))

    def test_distinct_creation_date_provenance(self):
        html = '''<dl><div><dt>Documento</dt><dd>ZAGALETA_EstudioDeDetalle</dd></div>
        <div><dt>Formato</dt><dd>PDF</dd></div>
        <div><dt>Fecha de creación</dt><dd>08-nov-2018 13:57:15</dd></div>
        <div><dt>Código CSV</dt><dd>REALCSV</dd></div>
        <div><dt>Verificación de integridad</dt><dd>HASH</dd></div></dl>
        <iframe src="/preview/pdf/signed.pdf"></iframe>'''.replace('HASH', 'a' * 128)
        meta = preview_metadata(html, 'ZAGALETA_EstudioDeDetalle')
        self.assertEqual(meta['fecha_creacion_documento_texto'], '08-nov-2018 13:57:15')
        self.assertNotIn('fecha_aprob', meta)
        with self.assertRaises(ValueError):
            preview_metadata(html, 'Other instrument')
        with self.assertRaises(ValueError):
            preview_metadata(html.replace('/preview/pdf/signed.pdf', 'https://example.org/file.pdf'), 'ZAGALETA_EstudioDeDetalle')

    def test_wicket_encoding_and_folder_counts(self):
        parsed = ajax_components('<ajax-response><component id="x" encoding="wicket1"><![CDATA[RIU [texto]^]]></component></ajax-response>')
        self.assertEqual(parsed['x'], 'RIU [texto]')
        self.assertEqual(folders('<a class="gIconLink exp">7.1. PLANEAMIENTO URBANÍSTICO <span>( 314 )</span></a>'), [('7.1. PLANEAMIENTO URBANÍSTICO', 314)])
        with self.assertRaises(ValueError):
            ajax_components('<html>Login</html>')
        with self.assertRaises(ValueError):
            folders('<a class="gIconLink exp">Changed folder</a>')

    def test_all_pages_and_explicit_end(self):
        a = FakeAdapter(['Portal de transparencia' + link(1, 'first') + MORE,
                         ajax(link(2, 'second')), ajax(link(3, 'last'), end=True)])
        docs = a._crawl(None, SOURCE, expected=3)
        self.assertEqual(len(docs), 3)
        self.assertEqual(a.inventory_counts[SOURCE]['total_documents'], 3)

    def test_incomplete_count_and_stalled_pagination_fail(self):
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            FakeAdapter(['Portal de transparencia' + link(1, 'first')])._crawl(None, SOURCE, expected=2)
        with self.assertRaisesRegex(ValueError, 'no progress'):
            FakeAdapter(['Portal de transparencia' + link(1, 'first') + MORE,
                         ajax(link(1, 'first'))])._crawl(None, SOURCE)
        with self.assertRaises(ValueError):
            FakeAdapter(['Login'])._crawl(None, SOURCE)

    def test_late_page_failure_preserves_previous_output(self):
        a = FakeAdapter(['<a class="gIconLink exp">7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (2)</a>',
                         'Portal de transparencia' + link(1, 'ZAGALETA_EstudioDeDetalle') + MORE,
                         '<html>Session expired</html>'])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'projects.jsonl'
            path.write_text('previous complete snapshot\n')
            with self.assertRaises(ValueError):
                a.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous complete snapshot\n')

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'licencias.jsonl'
            result = BenahavisAyuntamientoAdapter('benahavis').backfill_licencias(p)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(p.read_text(), '')


if __name__ == '__main__':
    unittest.main()
