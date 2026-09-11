# Castelló de Rugat — investigación portal ayuntamiento

**Municipio:** Castelló de Rugat (València / Valencia, Comunitat Valenciana)  
**Slug:** `castello-de-rugat`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.castelloderugat.es | **Operativa** — Drupal 10 Portales municipales (tema `portales`, Matomo site 87) |
| PGOU (noticia) | https://www.castelloderugat.es/noticia-pagina/pgou | **Operativa** — memoria, normas y planos PDF del PGOU |
| PGOU (contenido) | https://www.castelloderugat.es/content/pgou | Redirige / menú urbanismo |
| Planos municipales | https://www.castelloderugat.es/pagina/plans-municipals | Enlace menú (timeouts intermitentes desde CI) |
| Plano calles | https://www.castelloderugat.es/pagina-enlace/planol-carrers | PDF plano calles |
| Sede electrónica | https://castelloderugat.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://castelloderugat.sedelectronica.es/board | **Operativa** — 1 fila (no urbanismo) |
| Catálogo trámites | https://castelloderugat.sedelectronica.es/dossier | Licencias urbanísticas, certificados, ocupación vía sede |
| Consulta expedientes | https://castelloderugat.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| GVA planeamiento | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46219%20RUGAT | Documentación PG 2002 + modificación nº6 2019 |

## PGOU (Drupal)

La página `/noticia-pagina/pgou` publica documentación del Plan General en PDF:

- Memoria justificativa PGOU
- Índex / normes urbanístiques
- Planols 1, 3, 7, 8, 9A–9C (classificació, qualificació, dotacions, altures)
- Catàleg de bens arquitectònics

- **CMS:** Drupal 10 Portales (`/themes/portales`).
- **Listado:** HTML estático con enlaces `/sites/www.castelloderugat.es/files/*.pdf`.
- **Limitación:** handshake SSL intermitente desde CI; el adapter reintenta con backoff.

## Tablón sede (espublico gestiona)

- Plataforma Wicket (mismas clases CSS que Benigànim, Enguera, Alfafar).
- Contenido actual (ene 2025): edicto jurado — **sin filas urbanísticas**.
- Trámites destacados en sede: «Solicitud de Licencia o Autorización Urbanística», «Certificado o Informe Urbanístico», «Licencia de Ocupación».

## Licencias de obra

- No hay dataset público de concesiones históricas de licencia de obra.
- Trámites vía sede `/dossier` (sin listado histórico).
- El adapter incluye páginas informativas del tablón y catálogo de trámites (patrón Pozuelo/Benigànim).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS zonificación: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, `cod_ine_mun=46219` (nombre ICV: «Rugat»; **no** usar 46090 del DOGV).
  - Plan general homologado: expediente `20190164`, fid `11996`, 213 polígonos de zonificación.
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
  - Plano calles: PDF estático (`/pagina-enlace/planol-carrers`), sin enlace a expedientes.
- **Estrategia:** consulta WFS por `featureId` / paginación filtrada por `cod_ine_mun=46219`; geometría asociada al instrumento de planeamiento (PG), no a licencias individuales.
- **Limitaciones:** CQL_FILTER del WFS no funciona en servidor (filtrado cliente); sin visor municipal ArcGIS; licencias solo PDF/sede sin georreferencia; handshake SSL intermitente en web Drupal.

## Limitaciones generales

- Web Drupal con timeouts SSL ocasionales en CI (requiere reintentos).
- Tablón sede sin entradas urbanísticas en el momento de la investigación.
- Consulta de expedientes requiere login.
- Geometría parcial: solo zonificación PG vía ICV, no polígonos por expediente de licencia.

## Adapter implementado

- `municipio.adapters.castello_de_rugat:CastelloDeRugatAyuntamientoAdapter`
- Fuentes: PGOU PDFs Drupal + tablón sede + ICV WFS + trámites informativos.
- IDs: `castello-de-rugat-lic-*` / `castello-de-rugat-proy-*` (sha256[:14]).
