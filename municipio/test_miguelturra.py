import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.miguelturra import (
    SOURCE, MiguelturraAyuntamientoAdapter, group_instruments, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest


def inventory(title='Plan de Ordenación Municipal 2007', path='/ordenanzas/pom', pager=''):
    return f'<div class="view-ordenanzas"><h2 class="teaser__headline"><a href="{path}">{title}</a></h2>{pager}</div>'


def detail(title, body='', documents=('pom.pdf',)):
    links = ''.join(f'<a href="/sites/default/files/ordenanzas_archivos/{d}">{d}</a>' for d in documents)
    return f'<article class="node"><h1 class="field--name-title">{title}</h1><div class="field--name-body">{body}</div><div class="field--name-field-ordenanzas-archivo">{links}</div></article>'


class MiguelturraTests(unittest.TestCase):
    def test_publication_and_agreement_are_distinct(self):
        title = 'Modificación puntual del Plan de Ordenación Municipal número 7/2018 (BOP 2025-08-28)'
        row = parse_detail(detail(title, 'en sesión de fecha 31 de julio de 2018 acordó aprobar definitivamente la modificación'), SOURCE, title)
        self.assertEqual(row['fecha_publicacion'], '2025-08-28')
        self.assertEqual(row['fecha_aprob'], '2018-07-31')
        self.assertEqual(row['fecha_acuerdo'], '2018-07-31')
        self.assertNotIn('fecha', row)

    def test_public_consultation_is_not_approval(self):
        title = 'Modificación puntual número 8 del Plan de Ordenación Municipal'
        body = 'Anuncio de 16/02/2022. Decreto de la Alcaldía nº 2022/150 de fecha 15 de Febrero de 2022, se ha resuelto someter a información pública'
        row = parse_detail(detail(title, body), SOURCE, title)
        self.assertEqual(row['fecha_acuerdo'], '2022-02-15')
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fecha_publicacion', row)

    def test_group_documents_and_keep_provenance(self):
        titles = ['Plan de Ordenación Municipal 2007', 'Correción de errores del POM de Marzo de 2008']
        rows = [parse_detail(detail(t, documents=(f'{n}.pdf',)), f'https://www.miguelturra.es/ordenanzas/{n}', t) for n, t in enumerate(titles)]
        grouped = group_instruments(rows)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]['documentos']), 2)
        self.assertEqual(len(grouped[0]['source_urls']), 2)
        self.assertNotIn('fecha_aprob', grouped[0])
        self.assertIsNone(grouped[0]['lat'])

    def test_reject_empty_login_mismatched_and_documentless_pages(self):
        with self.assertRaises(ValueError):
            parse_inventory('<form>Login</form>')
        for html in ['<form>Login</form>', detail('Other title'), detail('Plan de Ordenación Municipal', documents=())]:
            with self.assertRaises(ValueError):
                parse_detail(html, SOURCE, 'Plan de Ordenación Municipal')
        with self.assertRaises(ValueError):
            parse_inventory(inventory(path='https://example.com/ordenanzas/fake'))

    def test_exclude_forms_news_and_parcel_sheet(self):
        for title in ['Solicitud de licencia de obras', 'Normas urbanísticas referentes a parcelas', 'Noticias de Miguelturra']:
            with self.assertRaises(ValueError):
                parse_inventory(inventory(title))

    def test_follow_pagination_and_refresh_snapshot(self):
        page2 = SOURCE + '?page=1'
        first = inventory(pager=f'<nav class="pager"><a href="{page2}">Siguiente</a></nav>')
        second = inventory('Modificación puntual del POM de Enero de 2009', '/ordenanzas/mod')
        sources = {SOURCE: first, page2: second,
                   'https://www.miguelturra.es/ordenanzas/pom': detail('Plan de Ordenación Municipal 2007'),
                   'https://www.miguelturra.es/ordenanzas/mod': detail('Modificación puntual del POM de Enero de 2009')}
        adapter = MiguelturraAyuntamientoAdapter('miguelturra')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            out = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
        with self.assertRaises(ValueError):
            parse_inventory(inventory(pager='<nav class="pager"><a href="https://example.com/next">Next</a></nav>'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('miguelturra')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = MiguelturraAyuntamientoAdapter('miguelturra').backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
