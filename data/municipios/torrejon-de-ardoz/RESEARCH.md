# Torrejón de Ardoz — investigación portal ayuntamiento

**Fecha:** 2026-06-17  
**Slug:** `torrejon-de-ardoz`  
**BOCM (referencia):** 149 filas

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (Drupal 10) | https://www.ayto-torrejon.es | Accesible |
| Sede electrónica (plataforma Ayto) | https://sede.ayto-torrejon.es | Accesible |
| Dominio legacy | https://www.torrejondeardoz.es | 403 (WAF/Fortinet) — no usar |

## Fuentes de planeamiento y licencias

### 1. Tablón Virtual — Urbanismo (principal)

- **URL:** https://sede.ayto-torrejon.es/portal/tablonVirtual.do?subseccion=TABURB&opc_id=175&ent_id=1&idioma=1
- **Formato:** HTML tabular (plataforma sede Ayto, Bootstrap + Dojo)
- **Contenido:**
  - Tabla **Expedientes** con columnas: Año, Código, Tipo, Nombre, Fecha creación, Fecha publicación, Estado
  - Tipos observados: `URB_LICENCIAS DE ACTIVIDADES CALIFICADAS`, `URB_LICENCIAS DE ACTIVIDADES INOCUAS`
  - Enlace a detalle por `expId=<id>` con subtabla **Documentos** (edictos `URB_OU_EDICTO …`)
- **Filtros:** estado (Todos / Sin Estado), fechas, descripción (POST)
- **Paginación:** no visible en muestra actual (~7 expedientes activos)
- **Sección Documentos** del índice TABURB: vacía (`No se han encontrado documentos`); los PDFs están en el detalle de cada expediente

### 2. Otras subsecciones del Tablón Virtual

| Subsección | Código | Contenido urbanístico |
|------------|--------|------------------------|
| Información | INFOTAB | Sin expedientes urbanismo relevantes |
| Intervención | TABINTER | Sin urbanismo |
| Tributos | TRIBTAB | Sin urbanismo |

### 3. Web Drupal — urbanismo y trámites (complementaria)

- https://www.ayto-torrejon.es/concejalias/urbanismo — PDFs normativos (plano oficial, carta de servicios)
- https://www.ayto-torrejon.es/tramites/licencias-y-gestiones-urbanisticas — índice de trámites (sin listado de concesiones)
- **Formato:** HTML Drupal con enlaces a `/sites/default/files/*.pdf`
- **Limitación:** no publica registro histórico de licencias concedidas; solo documentación informativa

### 4. Trámites electrónicos (no scrapeables sin auth)

- Catálogo sede: licencia de obra, declaración responsable, consulta urbanística, etc.
- Requieren certificado / Cl@ve para presentación; no exponen listado público de expedientes tramitados

## Estrategia de ingesta

| Dataset | Fuente | Criterio |
|---------|--------|----------|
| `licencias.jsonl` | Tablón TABURB expedientes | Tipos `URB_LICENCIAS*`; `fecha_concesion` = fecha publicación |
| `proyectos.jsonl` | Detalle expedientes (edictos) + PDFs Drupal urbanismo | Edictos y documentos de planeamiento/normativa |

## Limitaciones

- Sin API JSON pública; scrape HTML determinista
- Listado TABURB muestra solo expedientes recientes/activos (no histórico completo)
- Sin coordenadas (`lat`/`lon`) ni distrito en el tablón
- `www.torrejondeardoz.es` bloqueado desde algunos entornos (WAF)
- Documentos del tablón requieren `codVerif` por enlace; se conserva URL de detalle del expediente como `url` estable

## Referencias

- Adapter: `municipio.adapters.torrejon_de_ardoz:TorrejonDeArdozAyuntamientoAdapter`
- Patrón similar a: Getafe (sede tablón) + Pozuelo (Drupal PDFs semilla)
