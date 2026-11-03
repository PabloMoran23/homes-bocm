import assert from "node:assert/strict";
import { normalizarActuacionEdificio } from "./lib/actuacion-edificio.mjs";

for (const separator of [" ", " - "]) {
  assert.equal(normalizarActuacionEdificio({ tipoExpediente: `Declaración Responsable${separator}Actividad` }).codigo, "local_actividad");
  assert.equal(normalizarActuacionEdificio({ tipoExpediente: `Declaración Responsable${separator}Residencial` }).codigo, "vivienda_obra_menor");
}
console.log("Current municipal CSV categories OK");
