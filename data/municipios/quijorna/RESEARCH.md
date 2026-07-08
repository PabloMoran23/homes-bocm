# Quijorna — investigación portal ayuntamiento

**Municipio:** Quijorna (`quijorna`)  
**Comunidad:** Comunidad de Madrid  
**BOCM:** 18 proyectos históricos en CSV  

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress citygov) | https://aytoquijorna.org |
| Urbanismo | https://aytoquijorna.org/concejalias/urbanismo/ |
| Trámites y gestiones (22 PDF guías) | https://aytoquijorna.org/concejalias/urbanismo/tramites-y-gestiones-de-urbanismo/ |
| Licencias urbanísticas (informativo) | https://aytoquijorna.org/concejalias/urbanismo/licencias-urbanisticas/ |
| Normativa urbanística | https://aytoquijorna.org/concejalias/urbanismo/normativa-urbanistica/ |
| Zonas de ordenanza | https://aytoquijorna.org/concejalias/urbanismo/zonas-de-ordenanza/ |
| Sede electrónica (espublico gestiona / eHome) | https://aytoquijorna.sedelectronica.es/ |
| Tablón general | https://aytoquijorna.sedelectronica.es/board/ |
| Tablón categoría Urbanismo | https://aytoquijorna.sedelectronica.es/board/974e6d5e-f59b-11de-b600-00237da12c6a/ |
| Transparencia — Normas Subsidiarias Tomo II | https://aytoquijorna.sedelectronica.es/transparency/c3bde2cb-3329-460a-9b0b-d02e55dc25f5/ |
| Catálogo trámites sede | https://aytoquijorna.sedelectronica.es/dossier |

## Cómo se listan expedientes / proyectos

- **Tablón eHome (Wicket/HTML):** tabla con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha; enlaces `preview-document/{uuid}`. El tablón general tiene ~4 anuncios (mayoría no urbanísticos). La categoría Urbanismo está **vacía** (tbody sin filas).
- **Transparencia:** carpeta fija con 10 PDFs del Tomo II de Normas Subsidiarias de Planeamiento (capítulos 1–10). HTML estático parseable.
- **WordPress:** guías PDF de tramitación (jun 2026) y enlace BOCM a aprobación normas subsidiarias (`BOCM-20210430-21.PDF`).
- **Consulta expedientes:** `/expedientes` requiere identificación Cl@ve; no hay listado público.

## Cómo se publican licencias

- No hay dataset ni listado histórico de concesiones.
- Trámites vía sede electrónica (URB-001A declaración responsable / licencia).
- Guías PDF en web describen procedimientos (obras mayores/menores, segregaciones, etc.).
- El adapter incluye páginas informativas + guías PDF como filas de referencia; concesiones futuras aparecerán en tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - [Visor SIT Comunidad de Madrid](https://www.comunidad.madrid/medio-ambiente/sistema-informacion-territorial-visor-sit) — planeamiento refundido por municipio.
  - WFS GeoServer CM: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='QUIJORNA'`.
  - Ejemplo ámbito: `S-01R DEHESA BOYAL`.
- **Estrategia:** enriquecimiento post-scrape vía `geometry.enrichers: sitcm_ambito` cuando el título cita código de ámbito (AA, UE, S-01R, etc.). Los PDFs de normativa no enlazan polígonos por expediente.
- **Limitaciones:**
  - Sin visor urbanístico municipal propio.
  - Tablón/PDF sin georreferencia por licencia.
  - Certificado SSL inválido en `aytoquijorna.sedelectronica.es` (`insecure_ssl: true` en adapter).
  - No hay ArcGIS/GeoJSON municipal enlazado a expedientes.

## Limitaciones generales

- Tablón urbanismo vacío en el momento de la investigación.
- Sede con TLS roto en entornos estrictos (curl sin `-k` falla).
- Portal transparencia usa árbol AJAX Wicket para navegar; se usan URLs de carpeta conocidas.
- Paginación del tablón no probada (pocos registros actuales).

## Patrón CMS

WordPress **citygov** + **espublico eHome** — mismo stack que Brunete, Humanes, Villanueva del Pardillo. Ver memoria `ehome-joomla-vvapardillo.md` / `wordpress-espublico-el-molar.md`.
