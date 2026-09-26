# Mancomunidad de Municipios de la Safor — investigación portal

Entidad: **Mancomunidad de Municipios de la Safor** (`mancomunidad-de-municipios-de-la-safor`) — Comunitat Valenciana, comarca Safor. Boletín: `dogv` (1 aviso).

## Contexto

No es un municipio unitario sino una **mancomunitat** de 31 municipios de la comarca de la Safor (capital Gandía). Los estatutos contemplan competencias urbanísticas delegadas, pero el portal web actual se centra en **servicios sociales compartidos** (CDIAP, SAD, carpa, agua en alta, etc.), no en expedientes de planeamiento ni licencias de obra de los ayuntamientos miembros.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.mancomunitat-safor.es |
| Disposiciones normativas | https://www.mancomunitat-safor.es/pagina/disposicions-normatives |
| Consulta audiencia pública | https://www.mancomunitat-safor.es/pagina/consulta-audiencia-publica |
| Trámites / formularios | https://www.mancomunitat-safor.es/pagina/tramits |
| Sede electrónica | https://mancomunitatdelasafor.sedelectronica.es (indeterminada) |
| Transparencia (sede) | https://mancomunitatdelasafor.sedelectronica.es/transparency/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** Drupal (tema `portales` / Adaptive Theme).
- **Sin sección de urbanismo** ni tablón de expedientes urbanísticos en el portal.
- **Normativa:** PDFs enlazados desde `/pagina/disposicions-normatives` (estatutos, reglamentos de servicios, ordenanzas fiscales, planes estratégicos).
- **Agenda Urbana:** PDF «Agenda Urbana Mancomunitat Safor» (modificación objetivo 02, ple 24-03-2026) — documento estratégico comarcal, no expediente con ámbito parcelario.
- **Consulta audiencia pública:** anuncios de reglamentos de servicios sociales (PEIs, SAD, Cuina que Cuida, etc.); ninguno es planeamiento urbanístico individualizado.
- **Sede electrónica:** responde «Sede Electrónica Indeterminada» (sin tablón ni dossier de trámites urbanísticos configurado).

## Licencias de obra

- **Sin dataset** de licencias concedidas.
- **Sin trámites** de licencia de obra en el catálogo de la mancomunitat (solo formularios de servicios sociales, carpa, casetas, instancia general).
- Las licencias urbanísticas corresponden a los **31 ayuntamientos miembros** (Gandía, Oliva, Daimús, etc.), no a la mancomunitat.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - Portal mancomunitat-safor.es: sin visor urbanístico ni datos abiertos GIS.
  - Sede electrónica: no operativa (página de selección).
  - ICV terramapas (`terramapas.icv.gva.es/0702_Planeamiento`): capas por municipio INE, no por mancomunitat; sin enlace a expedientes de la entidad.
  - Agenda Urbana PDF: documento estratégico sin geometría vectorial enlazable.
- **Estrategia:** no hay query por código de expediente ni WFS/ArcGIS de la mancomunitat. El orquestador aplicará centroide comarcal (Gandía) + jitter.
- **Limitaciones:** entidad supramunicipal; planeamiento urbanístico municipal no agregado en un único portal.

## Limitaciones generales

- Portal orientado a servicios sociales y empleo; urbanismo limitado a Agenda Urbana estratégica.
- Sede electrónica sin configurar (SSL también falla en `www.` subdominio).
- Sin licencias ni expedientes urbanísticos publicados en listado scrapeable.
- El aviso DOGV probablemente corresponde a la Agenda Urbana o actuación normativa comarcal, no a un sector con polígono.
