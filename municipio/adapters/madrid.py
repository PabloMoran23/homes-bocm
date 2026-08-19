"""Madrid capital: SIGMA + visor/NTI + licencias open data, mismo contrato JSONL que el resto."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.madrid_export import VISOR_JSON, export_licencias, export_proyectos, SIGMA_INDEX, JSONL_LIC
from municipio.manifest import POC_ROOT, load_manifest

SIGMA_MODULE = "sector_geometry.madrid_ayto_sync"
VISOR_MODULE = "sector_geometry.madrid_viso_fetch"
LICENCIAS_MODULE = "sector_geometry.madrid_licencias_download"


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val or "").strip().lower() in ("1", "true", "yes", "sí", "si")


class MadridAyuntamientoAdapter(AyuntamientoAdapter):
    """Envuelve los scrapers SIGMA/visor/licencias y exporta al JSONL común."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(
            slug,
            config,
            base_url or "https://geoportal.madrid.es/IDEAM_WBGEOPORTAL/visor_planeamiento.iam",
        )
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.visor_since_year = int(
            self.config.get("visor_since_year") or (datetime.now(UTC).year - 2)
        )
        self._proyectos_scraped = False
        self._licencias_scraped = False

    def _skip_fetch(self) -> bool:
        return _truthy(self.config.get("skip_fetch")) or _truthy(os.environ.get("MADRID_SKIP_FETCH"))

    def _skip_visor(self) -> bool:
        return _truthy(self.config.get("skip_visor")) or _truthy(os.environ.get("MADRID_SKIP_VISOR"))

    def _refresh_licencias(self) -> bool:
        if _truthy(self.config.get("skip_licencias")):
            return False
        if _truthy(os.environ.get("MADRID_LICENCIAS")):
            return True
        return _truthy(self.config.get("refresh_licencias"))

    def _run(self, module: str, args: list[str]) -> None:
        cmd = [sys.executable, "-m", module, *args]
        print(f"madrid: {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, cwd=str(POC_ROOT), check=True)

    def _export_proyectos(self) -> dict[str, Any]:
        return export_proyectos(load_manifest(self.slug))

    def _export_licencias(self) -> dict[str, Any]:
        return export_licencias(load_manifest(self.slug))

    def _sync_sigma(self) -> None:
        args: list[str] = []
        if self._skip_fetch() and SIGMA_INDEX.is_file():
            args.append("--skip-fetch")
        self._run(SIGMA_MODULE, args)

    def _sync_visor(self, *, incremental: bool) -> None:
        if self._skip_visor():
            return
        year = str(self.visor_since_year)
        delay = str(self.delay_s)
        if incremental:
            self._run(
                VISOR_MODULE,
                ["--fetch-missing-index", "--merge-existing", "--skip-nti", "--delay", delay],
            )
            self._run(
                VISOR_MODULE,
                [
                    "--refresh-since-year",
                    year,
                    "--merge-existing",
                    "--skip-nti",
                    "--delay",
                    delay,
                ],
            )
            self._run(
                VISOR_MODULE,
                [
                    "--enrich-ficha",
                    "--fetch-missing-html",
                    "--since-year",
                    year,
                    "--delay",
                    delay,
                ],
            )
            return
        self._run(VISOR_MODULE, ["--all-index", "--merge-existing", "--skip-nti", "--delay", delay])
        self._run(
            VISOR_MODULE,
            ["--enrich-ficha", "--fetch-missing-html", "--delay", delay],
        )

    def _sync_licencias(self, *, years: str | None, merge: bool) -> dict[str, Any]:
        if not self._refresh_licencias():
            if JSONL_LIC.is_file():
                return {"skipped": True, "reason": "licencias existentes; MADRID_LICENCIAS no activo"}
            return {"skipped": True, "reason": "sin madrid_licencias.jsonl y MADRID_LICENCIAS no activo"}
        args: list[str] = []
        if years:
            args.extend(["--years", years])
        if merge:
            args.append("--merge-jsonl")
        self._run(LICENCIAS_MODULE, args)
        return {"status": "ok", "years": years, "merged": merge}

    def _write_state(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        if not self._proyectos_scraped:
            self._sync_sigma()
            self._sync_visor(incremental=VISOR_JSON.is_file())
            self._proyectos_scraped = True
        exported = self._export_proyectos()
        return {**exported, "scrape": "sigma+visor_full"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        if not self._proyectos_scraped:
            self._sync_sigma()
            self._sync_visor(incremental=True)
            self._proyectos_scraped = True
        exported = self._export_proyectos()
        self._write_state(
            state_path,
            {
                "last_run": datetime.now(UTC).isoformat(),
                "count": exported.get("proyectos", 0),
                "adapter": self.__class__.__name__,
            },
        )
        return {**exported, "scrape": "sigma+visor_incremental"}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        if not self._licencias_scraped:
            lic = self._sync_licencias(years=None, merge=False)
            self._licencias_scraped = True
        else:
            lic = {"skipped": True, "reason": "ya descargadas en este proceso"}
        exported = self._export_licencias()
        return {
            "rows": exported.get("licencias", 0),
            "status": "ok",
            "download": lic,
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        year = datetime.now(UTC).year
        if not self._licencias_scraped:
            lic = self._sync_licencias(years=f"{year - 1},{year}", merge=True)
            self._licencias_scraped = True
        else:
            lic = {"skipped": True, "reason": "ya descargadas en este proceso"}
        exported = self._export_licencias()
        self._write_state(
            state_path,
            {
                "last_run": datetime.now(UTC).isoformat(),
                "count": exported.get("licencias", 0),
                "download": lic,
            },
        )
        return {
            "rows": exported.get("licencias", 0),
            "status": "ok",
            "download": lic,
        }
