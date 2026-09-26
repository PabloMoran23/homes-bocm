# Mancomunitat de Municipis de la Costera-Canal — investigación portal

Entidad: **Mancomunitat de Municipis de la Costera-Canal** (`mancomunitat-de-municipis-de-la-costera-canal`) — Comunitat Valenciana, comarca Costera-Canal (provincia Valencia). Boletín: `dogv` (1 aviso).

## Contexto

Mancomunitat supramunicipal de **18 localidades** de la comarca Costera-Canal (sede en Xàtiva). Presta servicios compartidos (urbanismo delegado, PMUS, obras públicas, medio ambiente). Los ayuntamientos miembros mantienen sus propios portales y sedes; la mancomunitat concentra documentación de **Planes de Movilidad Urbana Sostenible (PMUS)** y transparencia normativa.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.lacosteracanal.es |
| Urbanismo, Obras Públicas y Medio Ambiente | https://www.lacosteracanal.es/es/transparencia/urbanismo-obras-publicas-medio-ambiente |
| Planes y programas | https://www.lacosteracanal.es/es/transparencia/planes-programas |
| Transparencia | https://www.lacosteracanal.es/es/transparencia |
| Sede electrónica (Dival/Sedipualba) | https://lacosteracanal.sede.dival.es |
| Tablón de anuncios | https://lacosteracanal.sede.dival.es/tablondeanuncios/ |
| Tablón RSS | https://lacosteracanal.sede.dival.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo de servicios | https://lacosteracanal.sede.dival.es/catalogoservicios.aspx |

## Cómo se listan expedientes / planeamiento

- **CMS:** Drupal 10 (tema `portales` / Adaptive Theme, Matomo site 18).
- **Urbanismo transparencia:** listado estático de PDFs PMUS por municipio miembro (noviembre 2022) + publicación BOP (`20221114_PUBLICACIÓN BOP.pdf`).
- **PMUS municipios:** Barxeta, Cerdà, La Font de la Figuera, Novetlè, La Granja de la Costera, El Genovés, Rotglà i Corberà, Llanera de Ranes, Vallés, Llocnou d'En Fenollet, Torrella.
- **Sin visor de expedientes** ni listado de información pública de planeamiento parcelario.
- **Tablón sede:** RSS activo; contenido reciente es contabilidad/BOP (cuenta general 2025), no urbanismo.
- **Catálogo sede:** trámites administrativos (registro, OMIC, protección datos); **sin licencias de obra** ni dossier urbanístico.

## Licencias de obra

- **Sin dataset** de licencias concedidas en portal ni sede.
- **Sin trámites** de licencia/obra en catálogo de la mancomunitat.
- Las licencias urbanísticas corresponden a los **18 ayuntamientos miembros** y sus sedes Dival individuales.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - Portal lacosteracanal.es: PMUS en PDF sin enlace GIS ni coordenadas.
  - Sede Dival: tablón sin anuncios urbanísticos georreferenciables.
  - ICV terramapas (`terramapas.icv.gva.es/0702_Planeamiento`): capas por municipio INE individual, no por mancomunitat; PMUS no indexados como polígonos enlazables.
- **Estrategia:** no hay query por código de expediente ni WFS/ArcGIS de la entidad. El orquestador aplicará centroide Xàtiva + jitter.
- **Limitaciones:** entidad supramunicipal; PMUS son documentos estratégicos PDF sin delimitación vectorial scrapeable.

## Limitaciones generales

- Portal orientado a transparencia y PMUS comarcales; sin expedientes urbanísticos individuales.
- Tablón sede con poca actividad urbanística reciente.
- El aviso DOGV probablemente corresponde a publicación BOP de PMUS (2022), no a sector con polígono.
- Sin licencias ni geometría en fuentes públicas de la mancomunitat.
