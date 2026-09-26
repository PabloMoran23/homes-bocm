# Utiel — investigación portal ayuntamiento

**Municipio:** Utiel (Valencia, Comunitat Valenciana)  
**Slug:** `utiel`  
**INE:** 46245  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial (Drupal 10 / Digital Value) | https://www.utiel.es | Operativa |
| Urbanismo | https://www.utiel.es/es/pagina/urbanismo | Sección áreas (enlace PGOU, PIC) |
| PGOU / modificaciones | https://www.utiel.es/es/pagina/plan-general-ordenacion-urbana | **Operativa** — PDFs PGOU 1986 + 8 modificaciones puntuales |
| Portal transparencia web | https://www.utiel.es/es/transparencia | Presupuestario (Digital Value); enlace sede |
| Sede electrónica (espublico gestiona) | https://utiel.sedelectronica.es | Operativa |
| Tablón de anuncios | https://utiel.sedelectronica.es/board | HTML tabla Wicket (~10 filas/página) |
| Catálogo trámites | https://utiel.sedelectronica.es/dossier | Redirige a dossier.0 |
| Transparencia sede | https://utiel.sedelectronica.es/transparency | Índice normativa |
| Sedipualba RSS | utiel.sedipualba.es | **No existe** (404) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento / PGOU | Página web con PDFs descargables (modificaciones nº 6–19, memoria, planos) |
| Edictos / IP | Tablón sede `/board` (Wicket HTML, paginación AJAX) |
| Expedientes urbanísticos | Consulta en sede requiere autenticación; sin listado público |

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia.
- Trámites vía sede electrónica (catálogo dossier); sin licencias en línea sin identificación.
- Edictos urbanísticos ocasionales en tablón cuando el ayuntamiento los publica.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa `ms:Planeamiento.Zonificacion`, `cod_ine_mun=46245`
  - Única denominación: «Normas subsidiarias» (exp. 19870073, featureId 8525)
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
  - Punto Información Catastral (PIC) en web municipal (sin API pública)
- **Estrategia:** fetch puntual WFS por `featureId=Planeamiento.Zonificacion.8525`; matching textual título↔«normas subsidiarias» / «PGOU» / «modificación» para seeds de planeamiento
- **Limitaciones:**
  - ICV solo expone zonificación PGOU (normas subsidiarias), no parcelas ni expedientes del tablón
  - Tablón paginado (scrape estático ≈10 anuncios recientes)
  - Sin visor urbanístico municipal con geometría por expediente
  - PDFs PGOU sin georreferencia embebida

## Limitaciones generales

- CMS Digital Value / portalesmunicipales.dival.es; sede espublico gestiona (no Sedipualba/Dival tablón RSS)
- Tablón actual (sep 2026) sin licencias urbanísticas explícitas; mayoría anuncios administrativos
- `/info.0` de sede devuelve redirect loop; usar `/board` directamente
- CQL_FILTER en WFS ICV no fiable; paginación por `startIndex` (~offset 10000 para Utiel)

## Adapter implementado

- `municipio.adapters.utiel:UtielAyuntamientoAdapter`
- Fuentes: tablón sede + seeds PGOU web (PDFs) + ICV WFS + páginas informativas trámites
- IDs: `utiel-lic-*` / `utiel-proy-*` (sha256[:14])
