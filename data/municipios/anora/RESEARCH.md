# Añora — investigación portal ayuntamiento

**Municipio:** Añora (Córdoba, Andalucía)  
**Slug:** `anora`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://anora.es | **Operativa** — WordPress Divi gestionado por eprinsa (Diputación Córdoba) |
| Documentos ayuntamiento | https://anora.es/ayuntamiento/documentos/ | **Operativa** — PGOU, planos, plan parcial Polígono Industrial Palomares |
| Sede electrónica | https://sede.eprinsa.es/anora | **Operativa** — SPA Ember (eprinsa) |
| Tablón de edictos | https://sede.eprinsa.es/anora/tablon-de-edictos | **Operativa** — SPA sin API pública |
| Trámites | https://sede.eprinsa.es/anora/tramites | Catálogo procedimientos |
| Expedientes | https://sede.eprinsa.es/anora/expedientes | Requiere Cl@ve/certificado |
| Transparencia | https://transparencia.anora.es/ | WordPress Divi (publicidad activa, plenos, datos abiertos) |
| Datos abiertos CKAN | https://anora-opendata.e-admin.es/ | **Operativa** — sin datasets de urbanismo/planeamiento |
| Impuestos e-admin | https://anora-misimpuestos.e-admin.es/ | Tributos municipales |
| Geoportal Diputación | https://www.dipucordoba.es/servicios-geoportal/ | Referencia cartográfica provincial |

## Cómo se listan expedientes / proyectos

- **Web documentos:** listado HTML estático con enlaces a PDFs locales (`/wp-content/uploads/…`) y Google Drive (PGOU completo: normas, 8 planos, modificación ARIs 3-4, plan parcial Polígono Industrial Palomares).
- **Noticias WP:** REST API `/wp-json/wp/v2/posts?search=pgou|planeamiento|urbanismo` — p. ej. «Anuncio Consulta Previa – Modificación PGOU» (2021-08-03).
- **Sede eprinsa:** tablón de edictos en SPA Ember; no expone API REST ni RSS accesible sin sesión.
- **Transparencia:** portal separado sin carpeta específica de planeamiento estructurada.
- **CKAN:** 30+ datasets (población, callejero, licitaciones) pero **ninguno** de planeamiento urbanístico.

### Documentos PGOU encontrados (ago 2026)

| Título | Tipo enlace |
|--------|-------------|
| Certificación acuerdo PGOU | PDF local |
| Normas urbanísticas PGOU | Google Drive |
| Planos 1–8 (estructura orgánica, ordenación estructural/completa) | Google Drive |
| Modificación puntual PGOU (ARIs 3 y 4) | Google Drive |
| Plan Parcial Polígono Industrial Palomares (memoria + plano parcelario) | Google Drive |
| Ordenanza suelo no urbanizable / actuaciones extraordinarias suelo rústico | PDF / BOP |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Tablón sede eprinsa publica edictos (licencias, notificaciones) vía SPA.
- Trámites de licencia/comunicación previa en sede (`/tramites`); sin histórico estructurado abierto.
- Ordenanza situación jurídica edificaciones en suelo no urbanizable disponible en documentos.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA (Junta de Andalucía): https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — visor regional PGOU; sin API REST por código de expediente municipal.
  - PGOU en Google Drive/PDF: cartografía rasterizada sin GeoJSON/WFS descargable.
  - Geoportal Diputación Córdoba: servicios cartográficos provinciales sin enlace a expediente del ayuntamiento.
  - CKAN municipal: callejero y edificios sin capa de planeamiento.
  - `mapserver.eprinsa.es` referenciado en CSP de la web; sin capa pública de expedientes para Añora.
- **Estrategia:** documentar PGOU como metadatos; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin WFS/ArcGIS REST con geometría por expediente.
  - Tablón sede sin scrape determinista (SPA Ember).
  - Planos PGOU solo como PDF/imágenes en Google Drive.

## Limitaciones generales

- Tablón eprinsa sin API pública (como La Carlota, Fernán Núñez, Priego).
- Consulta de expedientes requiere autenticación.
- Sin sección «Urbanismo» dedicada en menú web; documentación en `/ayuntamiento/documentos/`.
- CKAN sin datasets de planeamiento.

## Adapter implementado

- `municipio.adapters.anora:AnoraAyuntamientoAdapter`
- Fuentes: documentos web (PGOU/planos/ordenanzas) + WP REST + páginas informativas sede + referencia SITUA.
- IDs: `anora-lic-*` / `anora-proy-*` (sha256[:14]).
