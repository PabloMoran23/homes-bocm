# Salou — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Plone) | https://www.salou.cat |
| Minisite urbanisme | https://www.salou.cat/ca/la-ciutat-per-temes/urbanisme-i-planejament |
| Planejament vigent (POUM, PP, PE, PMU, gestió) | …/planejament/* |
| Projectes en desenvolupament / finalitzats | …/projectes-en-desenvolupament |
| Convenis urbanístics | …/convenis-urbanistics |
| Sede SIAC | https://seu.salou.cat/siac/ |
| Tablón de anuncios | https://seu.salou.cat/siac/Tablon.aspx |
| Expedientes en tramitación | https://seu.salou.cat/siac/Publicaciones.aspx?t=ET&viewall=Y |
| Catálogo trámites (obras) | https://seu.salou.cat/siac/Procedimientos.aspx |
| Edictes (web) | https://www.salou.cat/ca/ajuntament/govern-obert/edictes-i-tauler-danuncis → redirige a sede |

## Cómo se listan expedientes / proyectos

- **Tablón SIAC (`Tablon.aspx`):** tabla ASP.NET `GridViewRow` con columnas *Descripción*, *Fecha publicación*, enlace `DetalleTablon.aspx?id=…`. Mezcla edictos generales y urbanismo; el adapter filtra por palabras clave (planejament, DOGC, exposició, PEU, etc.) y excluye créditos presupuestarios / personal.
- **Web Plone:** árbol del minisite *Urbanisme i planejament* (modificacions puntuals, plans parcials/especials, projectes en desenvolupament). Páginas `documentFirstHeading` + PDFs enlazados; fechas en meta `DC.date.modified`.
- **Publicaciones ET:** índice de expedientes en tramitación (sin dataset JSON; filas en HTML cuando hay publicaciones activas).

## Licencias

- **No hay** listado público de licencias concedidas con dirección/coordenadas.
- El tablón puede incluir anuncios puntuales de obras; en la práctica casi todo el volumen son otros edictos.
- **Trámites SIAC** (`Procedimientos.aspx`): OBRAS MAYORES/MENORES, comunicación previa, primera ocupación, informes urbanísticos, etc. El adapter los expone como filas informativas (`min_rows: 0` aceptable en licencias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes revisadas:**
  - ICV WFS `ms:InventarioSuSuz` (`terramapas.icv.gva.es/0702_Planeamiento`): no se encontraron features con `cod_ine_mun=43148` (Salou) en muestras paginadas; instrumentos POUM publicados como PDF/planos en Plone.
  - Minisite incluye *Comparador històric del territori* (visor temporal) sin enlace API/WFS por expediente.
  - No hay visor ArcGIS municipal con query por código de expediente del tablón.
- **Estrategia:** metadatos sin `geom_geojson`; el orquestador usa bbox municipal en `manifest.yaml` + jitter en `geocode`.
- **Limitaciones:** delimitación de ámbitos solo en documentación PDF; tablón sin georreferencia.

## Limitaciones generales

- Tablón mezcla muchos edictos no urbanísticos; filtrado heurístico.
- Sede SIAC embebe menú completo de salou.cat (HTML pesado).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
