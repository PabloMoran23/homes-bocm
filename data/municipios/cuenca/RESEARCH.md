# Cuenca — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `cuenca` |
| CCAA | Castilla-La Mancha |
| Provincia | Cuenca |
| INE | 16078 |

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.cuenca.es |
| Gerencia Urbanismo (GMU) | https://gerenciaurbanismo.cuenca.es |
| Alias urbanismo | https://urbanismo.cuenca.es (mismo portal DNN) |
| Sede electrónica | https://sede.cuenca.es |
| Gobierno abierto | https://gobiernoabierto.cuenca.es |
| Impresos / formularios | https://ayuntamiento.cuenca.es/impresos-y-formularios |

### Páginas semilla (planeamiento / documentación)

- https://gerenciaurbanismo.cuenca.es/plan-general — capítulos PGOU (PDF en `www.cuenca.es/Portals/gerenciaurbanismo/files/`)
- https://gerenciaurbanismo.cuenca.es/planes-especiales — memoria, normas, planos calificación/ordenación (PDF/ZIP)
- https://gerenciaurbanismo.cuenca.es/plan-general-provisional
- https://gerenciaurbanismo.cuenca.es/ordenanzas-municipales
- https://gerenciaurbanismo.cuenca.es/catalogo-bic
- https://gerenciaurbanismo.cuenca.es/desarrollo-urbano-sostenible
- https://gerenciaurbanismo.cuenca.es/requisitos — instrucciones licencias (módulo `tablaIP` + PDFs)
- https://gerenciaurbanismo.cuenca.es/tablon-anuncios — módulo `tablaIP` (listado vacío: «No existen elementos»)

## Cómo se listan expedientes / proyectos

- **CMS:** DotNetNuke (Telerik) multi-portal `cuenca.es` (portal `gerenciaurbanismo`).
- **Planeamiento:** documentos estáticos enlazados en HTML (PDF/ZIP), no hay API JSON ni feed RSS específico de urbanismo.
- **Tablón de anuncios:** ASP.NET WebForms + módulo `desktopmodules/tablaIP/tablaIP_ascx`; requiere postback para filtros; el listado por defecto no devuelve filas en el HTML inicial.
- **Noticias:** `/noticias` sin RSS dedicado en GMU (RSS general en `www.cuenca.es/Portals/Cuenca/RSS/rss_noticias.aspx` es transversal).
- **Sede:** `sede.cuenca.es` — trámites electrónicos; no se localizó tablón público de expedientes urbanísticos indexable sin autenticación.

## Licencias de obra

- No hay dataset ni tablón de **licencias concedidas**.
- **Trámites informativos:** `/requisitos` (R-02OCO ocupación vía pública, R-03UPO usos/primera ocupación, etc.) y formularios en impresos (`F-03LU` licencia urbanística, `F-02OCO`, etc.).
- El adapter ingiere estas páginas/PDF como filas informativas (`min_rows` licencias vía trámites).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM `Planeamiento_Municipal/MapServer/0` — filtro `COD_INE='16078'`, campos `NOM_PLAN`, `PLAN_`, `DESCARGA`, geometría municipal PGOU (MultiPolygon WGS84).
  - No hay visor municipal ArcGIS enlazado a expedientes ni WFS de parcelas/expedientes en el portal GMU.
  - Gobierno abierto expone datos genéricos; sin capa de expediente urbanístico enlazable.
- **Estrategia:** query ArcGIS CLM por INE; adjuntar polígono PGOU a filas de plan general / calificación; resto sin geometría por expediente.
- **Limitaciones:** documentos PDF sin georreferencia; tablón sin filas; sin join expediente↔GIS.

## Limitaciones generales

- Tablón DNN vacío en scrape estático.
- Muchos PDFs con espacios en nombre de archivo (URL encoding).
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
