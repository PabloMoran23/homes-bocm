# Meco — investigación portal ayuntamiento

## Resumen

Municipio con **sede electrónica eAdmin** (`sede.ayto-meco.es`) y **portal de transparencia WordPress/Fusion** (`transparencia.ayto-meco.es`, solo HTTP; HTTPS con certificado inválido).

No hay visor de expedientes ni API REST pública. La ingesta se basa en documentos PGOU/planeamiento publicados en transparencia y trámites informativos de licencias en la sede.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Sede electrónica | `https://sede.ayto-meco.es/eAdmin/Sede.do` | eAdmin HTML | Acceso a tablón, trámites, validación documentos |
| Tablón de anuncios | `Tablon.do?action=inicioTablon` / `verAnuncios` | eAdmin HTML tabla | ~20 anuncios vigentes; sin licencias urbanísticas actuales |
| Trámites urbanísticos | `Registrar.do?action=inicioPortalTramites` (cat. 3) | eAdmin HTML | 7 trámites: obra mayor/menor, cédula, segregación, DR obras, calas, 1ª ocupación |
| Info trámite | `Registrar.do?action=infoTramite&tipoReg={id}` | eAdmin HTML | Descripción procedimiento (tipoReg 57–63) |
| Planeamiento | `transparencia.ayto-meco.es/?page_id=185` | WordPress Fusion | PGOU, modificaciones, Plan ALMA (~49 PDFs) |
| Planeamiento desarrollo | `?page_id=528` | WordPress Fusion | Planes especiales/parciales (~28 PDFs) |
| Instrumentos gestión | `?page_id=530` | WordPress Fusion | Convenios urbanísticos, reparcelación (~9 PDFs) |
| Documentos PDF | `ValidarDocumento.do?id_Documento={b64}&tipo=doc` | PDF directo | Enlaces `javascript:abrir('code')` en transparencia |

## Estructura HTML relevante

### Transparencia — documentos planeamiento

Cada documento en un `div.reading-box`:

```html
<a href="javascript:abrir('BonuJ0cM95M=')">ver documento</a>
<h2>... AprobacionPGOU-Meco-22oct2009</h2>
```

La función `abrir(codigo)` abre `ValidarDocumento.do?id_Documento={codigo}&tipo=doc` (devuelve PDF).

También hay breadcrumbs con título en el texto del enlace (`abrir('...')>TITULO</a>`).

### Tablón de anuncios

Tabla con celdas `width="40%"` (título) y fechas `DD/MM/YYYY`. Detalle en `Tablon.do?action=verAnuncio&id={hex}`. Búsqueda POST a `verAnuncios` con `referenciaBusqueda`.

### Trámites licencias (tipoReg)

| tipoReg | Trámite |
|---------|---------|
| 57 | Cédula urbanística |
| 58 | Segregación urbanística |
| 59 | Obra mayor |
| 60 | Obra menor |
| 61 | Calas o zanjas |
| 62 | Declaración responsable obras |
| 63 | Declaración responsable 1ª ocupación |

## Licencias

El ayuntamiento **no publica concesiones tabuladas** con coordenadas. Las filas de `licencias.jsonl` proceden de las páginas informativas de trámites urbanísticos (paridad mínima: procedimiento + URL sede). `lat`/`lon` = null.

## Limitaciones

- Portal transparencia: solo HTTP fiable; HTTPS falla verificación SSL.
- Tablón sin histórico urbanístico indexable (búsquedas de "licencia"/"urbanismo" devuelven 0 resultados).
- Documentos identificados por token base64 opaco (`id_Documento`), no por nombre de fichero.
- Sin geolocalización en fuentes del ayuntamiento.
- WP REST API deshabilitada (404).

## Referencia adapters

- Tablón eAdmin + filtrado regex: `mostoles.py`
- Trámites informativos licencias: `pozuelo.py` (`_collect_licencias_pages`)
- SSL inseguro transparencia: `getafe.py`
