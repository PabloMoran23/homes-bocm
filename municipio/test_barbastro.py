import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.barbastro import (
    SOURCE, BarbastroAyuntamientoAdapter, parse_detail, parse_inventory,
)


def article(body):
    return '<div class="com-content-article">' + body + '</div>'


INDEX = article('''<h1>Estudios de Detalle</h1><div itemprop="articleBody">
<a href="/component/content/article/1335-area-19?catid=51">Área 19. El Castillo (Terrero)</a>
<a href="/component/content/article/1335-area-19?catid=51">Área 19. El Castillo (Terrero)</a>
<a href="/component/content/article/1336-area-19?catid=51">Área 19. El Castillo (Tallada)</a>
</div>''')
DETAIL = article('''<div itemprop="articleBody">E.D. Área 19 El Castillo</div>
<ul class="jtcf_adjuntos"><a href="/attachments/article/1335/Memoria.pdf">Memoria.pdf</a></ul>
<a class="jtattach-filename" href="/images/jtattach/estudios-en-detalle/area19/memoria.pdf">
Memoria.pdf<span>(se abre en una pestaña nueva)</span></a>
<a class="jtattach-download" href="/images/jtattach/estudios-en-detalle/area19/memoria.pdf">Descargar</a>
<a class="jtattach-filename" href="/images/jtattach/estudios-en-detalle/area19/plano.pdf">Plano.pdf</a>
''')


class BarbastroTests(unittest.TestCase):
    def test_instruments_grouped_with_provenance_and_no_invented_dates(self):
        entries = parse_inventory(INDEX)
        self.assertEqual(len(entries), 2)
        row = parse_detail(DETAIL, entries[0])
        self.assertEqual(row['id'], 'barbastro-ed-1335')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['urls']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], entries[0]['url'])
        for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '22048')

    def test_fail_closed_on_pagination_empty_or_unrelated_content(self):
        for html in (INDEX + '<a rel="next" href="?start=20">Next</a>',
                     INDEX + '<div class="pagination"></div>',
                     article('<h1>Estudios de Detalle</h1><div itemprop="articleBody">Formulario</div>'),
                     INDEX.replace('/component/content/article/1335-area-19', 'https://example.org/1335')):
            with self.assertRaises(ValueError):
                parse_inventory(html)
        for detail in (article('<div itemprop="articleBody">Solicitud de licencia</div>'),
                       article('<div itemprop="articleBody">Estudio de Detalle</div>')):
            with self.assertRaises(ValueError):
                parse_detail(detail, parse_inventory(INDEX)[0])

    def test_full_snapshot_failure_preserves_previous_output(self):
        class Response:
            def __init__(self, url, text):
                self.url, self.text = url, text
            def raise_for_status(self):
                pass
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            def get(session, url, **kwargs):
                if url == SOURCE:
                    return Response(url, INDEX)
                if '1335-' in url:
                    return Response(url, DETAIL)
                raise RuntimeError('second instrument unavailable')
            with patch('requests.Session.get', get), patch('time.sleep'):
                with self.assertRaises(RuntimeError):
                    BarbastroAyuntamientoAdapter().backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        from municipio.manifest import load_manifest, load_yaml
        from municipio.adapters.registry import load_portal_adapter
        manifest = load_manifest('barbastro')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '22048')
        self.assertEqual(manifest.provincia, 'Huesca')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
