"""Offline parser and crawler regression tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pedro_munoz import (
    SOURCE, PedroMunozAyuntamientoAdapter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest

POM = 'Plan de Ordenacion Municipal de Pedro Muñoz'
CONVENIO = 'ACUERDO SOBRE CONVENIO URBANÍSTICO PARA MODIFICACION PUNTUAL NUM 6 DEL POM'
URL = 'https://www.pedro-munoz.es/urbanismo/pom/'


def listing(title=POM, url=URL, extra=''):
    return f'<h2 class="entry-title"><a href="{url}">{title}</a></h2>{extra}'


def detail(title=POM, text='', links=''):
    return (f'<h1 class="entry-title">{title}</h1>'
            '<time class="published" datetime="2020-06-25T16:43:34+02:00"></time>'
            f'<div id="penci-post-entry-inner" class="entry-content">{text}{links}</div>')


class PedroMunozTests(unittest.TestCase):
    def test_inventory_excludes_forms_news_and_tenders(self):
        html = listing() + listing('Solicitud licencia obra') + listing('Licitación de asistencia técnica')
        html += listing('Fiestas locales')
        rows, pages = parse_inventory(html)
        self.assertEqual(rows, {URL: POM})
        self.assertEqual(pages, set())

    def test_group_deduplicate_and_isolate_documents(self):
        a = '<a href="/wp-content/uploads/memoria.pdf">Memoria</a>'
        row = parse_detail(detail(text='Memoria', links=a+a), URL, POM)
        self.assertEqual(len(row['documentos']), 2)  # own HTML + one PDF
        other = parse_detail(detail(CONVENIO, 'Acuerdo', '<a href="//images/doc.pdf">Anuncio</a>'), URL, CONVENIO)
        self.assertIsNone(other['documentos'][1]['url'])
        self.assertEqual(other['documentos'][1]['href_original'], '//images/doc.pdf')
        self.assertNotIn('memoria.pdf', json.dumps(other))
        for key in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)

    def test_explicit_session_date_not_proposal_or_publication(self):
        text = ('El Ayuntamiento Pleno, en sesión ordinaria celebrada el día 14 de Mayo de 2020, '
                'adoptó el siguiente acuerdo. Propuesta de fecha 10 de Mayo de 2020.')
        row = parse_detail(detail(CONVENIO, text), URL, CONVENIO)
        self.assertEqual(row['fecha_acuerdo'], '2020-05-14')
        self.assertEqual(row['fecha_publicacion'], '2020-06-25')
        text = ('Certifica: en la sesión ORDINARIA celebrada por la PLENO de esta entidad local '
                'el día 27 de febrero de 2023, se adoptó el acuerdo.')
        row = parse_detail(detail(CONVENIO, text), URL, CONVENIO)
        self.assertEqual(row['fecha_acuerdo'], '2023-02-27')

    def test_pagination_fully_followed_and_deduplicated(self):
        page2 = SOURCE + 'page/2/'
        url2 = URL + 'modificacion/'
        pages = {SOURCE: listing(extra=f'<a class="page-numbers" href="{page2}">2</a>'),
                 page2: listing(CONVENIO, url2, f'<a rel="prev" href="{SOURCE}">Anterior</a>'),
                 URL: detail(text='POM', links='<a href="/memoria.pdf">Memoria</a>'),
                 url2: detail(CONVENIO, 'Acuerdo')}
        adapter = PedroMunozAyuntamientoAdapter('pedro-munoz')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'out.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len(out.read_text().splitlines()), 2)

    def test_fail_closed_and_preserve_previous_output(self):
        with self.assertRaises(ValueError):
            parse_inventory('<html>unavailable</html>')
        with self.assertRaises(ValueError):
            parse_inventory(listing(extra='<div class="penci-load-more"></div>'))
        with self.assertRaises(ValueError):
            parse_detail(detail(text='No documents'), URL, POM)
        adapter = PedroMunozAyuntamientoAdapter('pedro-munoz')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=listing()):
            out = Path(tmp) / 'out.jsonl'
            out.write_text('previous')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous')

    def test_manifest(self):
        manifest = load_manifest('pedro-munoz')
        self.assertEqual(manifest.nombre, 'Pedro Muñoz')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
