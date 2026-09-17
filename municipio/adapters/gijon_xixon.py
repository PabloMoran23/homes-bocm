"""Gijón/Xixón — alias slug del municipio Gijón (INE 33024)."""

from __future__ import annotations

import hashlib
from typing import Any

from municipio.adapters.gijon import GijonAyuntamientoAdapter

MUNICIPIO = "Gijón/Xixón"
ID_PREFIX = "gijon-xixon"


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


class GijonXixonAyuntamientoAdapter(GijonAyuntamientoAdapter):
    """Sede TAO + RPGUR Asturias; geometría parcial WFS (id_municipio=33024)."""

    def _collect_rpgur_proyectos(self) -> list[dict[str, Any]]:
        rows = super()._collect_rpgur_proyectos()
        for rec in rows:
            rec["municipio"] = MUNICIPIO
            origen = rec.get("origen", "rpgur")
            id_inst = rec.get("id_instrumento", "")
            rec["id"] = _stable_id("proy", f"{origen}:{id_inst or rec.get('titulo', '')}")
        return rows

    def _collect_sede_infopublica(self) -> list[dict[str, Any]]:
        rows = super()._collect_sede_infopublica()
        for rec in rows:
            rec["municipio"] = MUNICIPIO
            expediente = rec.get("expediente", "")
            titulo = rec.get("titulo", "")
            rec["id"] = _stable_id("proy", f"sede-ip:{expediente}:{titulo}")
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows = super()._collect_licencias()
        for rec in rows:
            link = rec.get("url", "")
            titulo = rec.get("titulo", "")
            rec["id"] = _stable_id("lic", link or titulo)
        return rows
