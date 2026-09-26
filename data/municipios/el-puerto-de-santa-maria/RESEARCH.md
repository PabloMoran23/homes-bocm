# El Puerto de Santa María — investigación portal ayuntamiento

Municipio: **El Puerto de Santa María** (`el-puerto-de-santa-maria`), provincia Cádiz, Andalucía. Boletín: BOJA (2 entradas).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://www.elpuertodesantamaria.es | CMS propio (Bootstrap, PHP) |
| Urbanismo | https://www.elpuertodesantamaria.es/areas-municipales/urbanismo-y-patrimonio/urbanismo/inicio-urbanismo-1 | Índice planeamiento |
| Info pública instrumentos | https://www.elpuertodesantamaria.es/areas-municipales/urbanismo-y-patrimonio/urbanismo/info-publica-instrumentos-de-planeamiento-y-gestion/informacion-publica-instrumentos-de-planeamiento-y-gestion | PDFs estudios detalle / BOP |
| PGOU 1992 | https://www.elpuertodesantamaria.es/areas-municipales/urbanismo-y-patrimonio/urbanismo/plan-general-de-ordenacion-urbana/plan-general-de-ordenacion-urbana-1 | Normativa y memoria PGOU |
| PGOM/POU | https://www.elpuertodesantamaria.es/areas-municipales/urbanismo-y-patrimonio/urbanismo/pgom-y-pou/plan-general-de-ordenacion-municipal-pgom-y-plan-de-ordenacion-urbana-pou | Planeamiento en tramitación |
| Planeamiento desarrollo | https://www.elpuertodesantamaria.es/areas-municipales/urbanismo-y-patrimonio/urbanismo/planeamiento-de-desarrollo-1/planeamiento-de-desarrollo | Planes parciales / especiales |
| Consulta previa | https://www.elpuertodesantamaria.es/areas-municipales/urbanismo-y-patrimonio/urbanismo/consulta-publica-previa/consulta-previa | Consultas previas |
| Sede electrónica | https://elpuertodesantamaria.sedelectronica.es | espublico gestiona (ehome) |
| Tablón | https://elpuertodesantamaria.sedelectronica.es/board | Wicket, preview-document (sin tabla clásica) |
| Trámites | https://elpuertodesantamaria.sedelectronica.es/dossier | Catálogo trámites urbanismo |
| Transparencia | https://transparencia.elpuertodesantamaria.es/exposicion-publica | Exposición pública (CMS transparencia) |
| Licencias urbanísticas | https://transparencia.elpuertodesantamaria.es/licencias-urbanisticas | Proyectos de actuación / licencias |
| Calificación ambiental | https://transparencia.elpuertodesantamaria.es/calificacion-ambiental-1 | Expedientes CA |
| Plan normativo | https://transparencia.elpuertodesantamaria.es/exposicion-publica/plan-normativo-audiencia-e-informacion-publica | Audiencia / información pública |

**Nota:** `elpuerto.sedelectronica.es` redirige a la sede activa `elpuertodesantamaria.sedelectronica.es`.

## Expedientes / proyectos

1. **Transparencia (exposición pública):** CMS dedicado con índice de documentos en periodo de exposición: estudios de detalle (CC-8 Gaonera, AER-23 La Rosa, VP1.1 Camino del Juncal), proyectos de actuación (enoturismo), calificación ambiental, urbanizaciones. Enlaces HTML y PDFs en `/uploads/`.
2. **Web municipal urbanismo:** PDFs de información pública de instrumentos (estudios detalle, BOP), PGOU 1992 refundido, PGOM/POU en tramitación, planeamiento de desarrollo.
3. **Tablón sede:** ~10 anuncios recientes en formato ehome (enlaces `preview-document` con atributo `title`). Incluye edictos de calificación ambiental y acuerdos de junta de gobierno con temas urbanísticos.
4. **Consulta expedientes:** Requiere identificación en sede; no hay listado público histórico de expedientes individuales.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en portal público.
- Sección **Licencias Urbanísticas** en transparencia con proyectos de actuación en exposición pública (enoturismo, certificados de pleno).
- Tablón sede puede publicar edictos de licencia/actividad puntuales.
- Trámites de licencia/DR/comunicación previa vía catálogo sede (`/dossier`).
- Adapter devuelve páginas informativas de tablón + transparencia licencias + catálogo trámites (patrón Pozuelo/Vera).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - ITACA (web municipal): visor Junta de Andalucía para toponimia de asentamientos, no expedientes urbanísticos.
  - VITUA/SITUA (Junta de Andalucía): planeamiento regional vigente; sin campo expediente del ayuntamiento ni API REST enlazable por código.
  - GeoCádiz (Diputación): cartografía provincial; sin capa de expedientes/licencias municipal.
  - Transparencia y sede: solo PDFs/HTML, sin coordenadas ni polígonos por expediente.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin visor urbanístico municipal con geometría enlazable a expediente; documentación en PDF sin georreferenciación pública.

## Limitaciones técnicas

- Tablón sede usa diseño ehome nuevo (sin filas `class_name` de tablas legacy); parseo vía `preview-document` + `title`.
- Transparencia en subdominio separado (`transparencia.elpuertodesantamaria.es`), distinto del CMS corporativo.
- Certificados SSL válidos; `insecure_ssl` no requerido.
- Web y transparencia accesibles desde CI sin bloqueo.
