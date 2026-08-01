# Robledo de Chavela — investigación portal ayuntamiento

**Slug:** `robledo-de-chavela`  
**Nombre oficial:** Robledo de Chavela  
**BOCM (referencia):** 13 anuncios  
**Fecha investigación:** 2026-07-25

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress) | https://robledodechavela.es | Accesible |
| Sede electrónica (Maggioli / eAdmin SPA) | https://robledodechavela.eadministracion.es | Accesible (Angular; tablón sin HTML scrapeable) |
| Sede legacy (espublico) | https://robledodechavela.sedelectronica.es | Inactiva («Sede Electrónica temporalmente inactiva») |
| Turismo | https://www.espaciorobledo.com | Accesible (sin urbanismo) |

## URLs base y páginas semilla

| Recurso | URL | Formato | Contenido |
|---------|-----|---------|-----------|
| Noticias / bandos | `/post-sitemap*.xml` → posts `informacion-*`, `bando-*` | WordPress HTML + PDF | Información pública, bandos de enajenación, ordenanzas suelo urbano |
| Información pública leña Monteagudillo | `/informacion-publica-lena-monteagudillo/` | WP + PDF | Expediente montes públicos |
| Bando barbacoas suelo urbano | `/bando-uso-de-barbacoas-en-suelo-urbano-2025/` | WP + PDF | Ordenanza uso suelo urbano |
| Entidades urbanísticas | `/robledo-aprueba-en-pleno-la-disolucion-de-varias-entidades-urbanisticas/` | WP noticia | Disolución entidades urbanísticas |
| BOCM aprobación inicial | `/wp-content/uploads/2024/03/20240327_Otros_BOCM-20240326-49-Informacion-publica-aprobacion-inicial.pdf` | PDF directo | Publicación BOCM planeamiento |
| PGOU (contratación) | Plataforma Contratación del Estado | Web licitación | Redacción Plan General (exp. 859/2023) |
| Catastro | `/catastro/` | WP estático | Enlace Sede Catastro (no expedientes locales) |
| Tablón / transparencia | `robledodechavela.eadministracion.es/home` | Angular SPA | Menú transparencia; API interna `api.atm-maggioli.es` sin acceso público directo |

## Proyectos / expedientes

- **Bandos de enajenación** de parcelas municipales (Doctor Pérez Suárez, Los Cerrillos, etc.) publicados como posts WP con PDF adjunto.
- **Información pública** montes (Monteagudillo, montes públicos).
- **BOCM** aprobación inicial (PDF en uploads).
- **PGOU**: licitación redacción Plan General (2023); sin visor ni documentación descargable en web municipal.
- **Noticias** disolución entidades urbanísticas, ampliación línea autobús a urbanización Canopus/Suiza.

No hay listado tabular de expedientes en información pública ni visor de seguimiento municipal.

## Licencias de obra

No hay registro público de concesiones con coordenadas.

Fuentes:

- Sede eAdmin Maggioli (trámites con identificación; SPA no expone listado HTML)
- Sede legacy espublico inactiva
- Bando uso barbacoas en suelo urbano (ordenanza, no concesión)

Estrategia adapter: páginas informativas de sede + bando urbanístico (como Pozuelo/Ajalvir).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='ROBLEDO DE CHAVELA'` (22 ámbitos: UA-0…UA-15, S-I…S-VI)
  - URL: `https://idem.comunidad.madrid/geoserver3/ows?service=WFS&typeName=sitcm:VPLA_V_AMBITO&CQL_FILTER=DS_MUNICIPIO='ROBLEDO DE CHAVELA'`
  - Sin visor urbanístico municipal propio ni ArcGIS del ayuntamiento
- **Estrategia:** matching por palabras clave / códigos UA en títulos (`Canopus`, `Suiza`, `Doctor Pérez Suárez` → UA-0, etc.) vía `resolve_ambito_geometry`
- **Limitaciones:** PDFs sin georreferencia; sede SPA sin API pública; muchos anuncios sin código de ámbito → sin polígono

## Limitaciones generales

- REST API WordPress bloqueada (`Solid Security` → 401)
- Sede `robledodechavela.sedelectronica.es` inactiva
- Sede `robledodechavela.eadministracion.es` es SPA Angular; `/eAdmin/Tablon.do` devuelve shell sin datos
- Sin histórico tabular de licencias concedidas
- WP REST no disponible; scraping vía sitemaps + HTML

## Referencia adapters

- WordPress + SITCM partial: `lozoyuela_navas_sieteiglesias.py`, `valdemorillo.py`
- eAdmin SPA sin tablón: `ajalvir.py` (documentación bloqueo)
- Trámites informativos licencias: `pozuelo.py`
