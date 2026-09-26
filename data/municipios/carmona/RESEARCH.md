# Carmona — investigación portal ayuntamiento

**Municipio:** Carmona (Sevilla, Andalucía)  
**Slug:** `carmona`  
**Web oficial:** https://www.carmona.org  
**Sede electrónica:** https://sede.carmona.org  

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Tablón de anuncios | https://www.carmona.org/actualidad/tablon.php | Publicaciones diarias (`publicacion.php?pub=<hash>`) |
| Planeamiento | https://www.carmona.org/planeamiento/ | Índice de NN.SS., modificaciones, PEPP, planes parciales |
| Normas subsidiarias | https://www.carmona.org/planeamiento/plan_normas_subsidiarias_mpales.php | Memoria, normas y planos (PDF) |
| Ordenanzas urbanísticas | https://www.carmona.org/ordenanzas/obras_me.pdf (y otras en /ordenanzas/) | Licencias obras menores, urbanización, etc. |
| Sede — trámites | https://sede.carmona.org/tramites | Licencias de obras, actividades municipales |
| Punto Información Catastral | https://www.carmona.org/servicios/pic/pic.php | PIC municipal (informativo) |

## Cómo se listan expedientes / proyectos

- **CMS propio PHP** (layout.css, sin Drupal/WordPress).
- **Tablón:** tabla HTML con enlaces `publicacion.php?pub=<md5>` y fecha `dd/mm/yyyy`. Calendario mensual en `diatablon.php?f=<unix_ts>` para histórico.
- **Planeamiento:** listado estático de enlaces a PDFs y subpáginas `plan_publ*.php`, `ficha_catalogo.php`. Sin API JSON.
- **Sede propia** (no espublico ni eprinsa): catálogo de trámites sin listado público de expedientes concedidos.

## Cómo se publican licencias

- No hay dataset ni tablón dedicado exclusivamente a licencias concedidas.
- Edictos de licencias/actividad aparecen mezclados en el tablón general (pocos en la muestra reciente).
- Trámites online en sede: "Licencias de Obras", "Inscripciones a Actividades Municipales".
- Ordenanza de obras menores publicada como PDF en `/ordenanzas/obras_me.pdf`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **SITUA/VITUA** (Junta de Andalucía): planeamiento general municipal (NN.SS. vigentes), sin capa de expedientes individuales ni consulta por código de expediente.
  - **CarmonaGIS** (https://www.carmonagis.org/): GeoNode comunitario (41 capas, datos abiertos varios); no enlaza expedientes urbanísticos del ayuntamiento.
  - **PIC municipal:** solo consulta catastral, sin geometría de proyectos.
  - **Web planeamiento:** documentos PDF sin georreferencia embebida consultable vía API.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [37.4712, -5.6461]`).
- **Limitaciones:** sin visor ArcGIS/WFS municipal; sede no expone coordenadas; tablón solo PDFs/HTML.

## Limitaciones generales

- Certificado SSL de carmona.org requiere `insecure_ssl: true` en algunos entornos.
- Tablón mezcla empleo/deportes con urbanismo; filtro por regex en adapter.
- Histórico de licencias concedidas no publicado de forma estructurada.
- Planeamiento vigente: Normas Subsidiarias 1983 adaptadas parcialmente a LOUA (sin PGOU/PBOM nuevo aún en tramitación 2025-2026).
