# San Fernando (Cádiz) — investigación portal ayuntamiento

**Slug:** `san-fernando`  
**Comunidad:** Andalucía  
**INE:** 11035  

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.sanfernando.es |
| Sede electrónica | https://sede.sanfernando.es |
| Tablón edictos (vigente) | https://sede.sanfernando.es/TablonAnuncios/TablonEdictos.asp?tipo=1&hidOptNav=76 |
| Tablón histórico | https://sede.sanfernando.es/TablonAnuncios/HistoricoTablonEdictos.asp?tipo=1&hidOptNav=76 |
| Trámites urbanismo (sede) | https://sede.sanfernando.es/Visor.asp?hidOptNav=125 |
| Planeamiento (web) | https://www.sanfernando.es/ayto/visor.asp?hidOptNav=1076 |
| PGOU (web) | https://www.sanfernando.es/ayto/visor.asp?hidOptNav=1182 |
| Otros instrumentos | https://www.sanfernando.es/ayto/visor.asp?hidOptNav=1278 |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## Cómo se listan expedientes / proyectos

- **Tablón de edictos (ASP clásico):** bloques `contieneAnuncio` con `tituloAnuncio`, rango de fechas en `infoAnuncio` y PDF en `www.sanfernando.es/tramites/Ficheros/Tablon/<id>/`.
- **Histórico:** misma plantilla en una sola página (~2400 entradas); filtro por regex urbanística en el adapter.
- **Planeamiento web:** páginas `visor.asp?hidOptNav=…` con enlaces FCKeditor a PDFs (PGOU, modificaciones, PMVS, PEPRICH, convenios).
- No hay API JSON ni visor de expedientes urbanísticos enlazado por código de expediente.

## Licencias de obra

- **No hay listado público** de concesiones de licencia con coordenadas.
- Anuncios de **calificación ambiental**, hostelería u ocupación vía tablón.
- **Trámites electrónicos** (declaración responsable 1211A/B, obra menor 1206, actividad 1215) en sede — páginas informativas / registro telemático SIGEM (`tramites.sanfernando.es`), sin histórico scrapeable.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Visor ArcGIS Hub municipal: https://visor-municipalidadsf.hub.arcgis.com/ (aplicación embebida; item de mapa no expone FeatureServer público consultable por código de expediente desde cloud).
  - SITUA (Junta de Andalucía): consulta documental PGOU/planeamiento, sin geometría REST enlazada al tablón municipal.
  - Zonas verdes (otro Hub): https://sanferverde-valorizasm.hub.arcgis.com/ — no urbanismo expedientes.
- **Estrategia:** el orquestador usará centroide municipal + jitter (`geocode`). Los títulos del tablón citan ámbitos (ARI, AIP, UE-53, SUS-02, etc.) pero no hay WFS municipal verificado en esta run.
- **Limitaciones:** tablón solo PDF; visor GIS sin capa pública queryable por expediente; charset ISO-8859-1 en sede.

## Limitaciones técnicas

- Histórico del tablón ~15–20 s de descarga; incluido con filtro urbanístico.
- Certificado SSL sede: `insecure_ssl: true` en manifest por compatibilidad.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
