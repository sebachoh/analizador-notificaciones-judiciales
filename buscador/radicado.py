"""Descomposición y validación del Código Único de Radicación (23 dígitos).

Estructura del código:

    66001  31  03  004  2026  00149  00
    │      │   │   │    │     │      └── instancia / recurso (2)
    │      │   │   │    │     └───────── consecutivo del proceso (5)
    │      │   │   │    └─────────────── año de radicación (4)
    │      │   │   └──────────────────── número del despacho (3)
    │      │   └──────────────────────── especialidad (2)
    │      └──────────────────────────── tipo de entidad (2)
    └─────────────────────────────────── municipio DANE (5), sus 2 primeros
                                          dígitos son el departamento
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date

from . import catalogos

LONGITUD = 23
_NO_DIGITOS = re.compile(r"\D")


class RadicadoInvalido(ValueError):
    """El texto suministrado no corresponde a un radicado de 23 dígitos."""


@dataclass(frozen=True)
class Radicado:
    completo: str
    municipio_codigo: str
    departamento_codigo: str
    entidad_codigo: str
    especialidad_codigo: str
    despacho_numero: str
    despacho_codigo: str  # 12 primeros dígitos: identifica el despacho exacto
    anio: str
    consecutivo: str
    instancia: str

    # --- Nombres legibles -------------------------------------------------
    @property
    def departamento(self) -> str:
        return catalogos.nombre_departamento(self.departamento_codigo)

    @property
    def municipio(self) -> str:
        return catalogos.nombre_municipio(self.municipio_codigo)

    @property
    def entidad(self) -> str:
        return catalogos.nombre_entidad(self.entidad_codigo)

    @property
    def especialidad(self) -> str:
        return catalogos.nombre_especialidad(self.especialidad_codigo)

    @property
    def formateado(self) -> str:
        r = self.completo
        return f"{r[0:5]}-{r[5:7]}-{r[7:9]}-{r[9:12]}-{r[12:16]}-{r[16:21]}-{r[21:23]}"

    @property
    def despacho_descripcion(self) -> str:
        """Ej.: 'JUZGADO DE CIRCUITO 004 CIVIL de PEREIRA (RISARALDA)'."""
        partes = [self.entidad, self.despacho_numero.lstrip("0") or "0"]
        if self.especialidad_codigo in catalogos.ESPECIALIDADES:
            partes.append(self.especialidad)
        return f"{' '.join(partes)} de {self.ubicacion}"

    @property
    def ubicacion(self) -> str:
        if self.municipio == self.departamento:  # Bogotá D.C. y similares
            return self.municipio
        return f"{self.municipio} ({self.departamento})"

    def to_dict(self) -> dict:
        datos = asdict(self)
        datos.update(
            {
                "formateado": self.formateado,
                "departamento": self.departamento,
                "municipio": self.municipio,
                "entidad": self.entidad,
                "especialidad": self.especialidad,
                "ubicacion": self.ubicacion,
                "despacho_descripcion": self.despacho_descripcion,
            }
        )
        return datos


def parsear(texto: str) -> Radicado:
    """Convierte cualquier forma escrita del radicado en un objeto `Radicado`.

    Acepta separadores arbitrarios: '66001-31-03-004-2026-00149-00',
    '66001 31 03 004 2026 00149 00' o los 23 dígitos seguidos.
    """
    if texto is None:
        raise RadicadoInvalido("Debe ingresar un número de radicado.")

    digitos = _NO_DIGITOS.sub("", str(texto))
    if not digitos:
        raise RadicadoInvalido("Debe ingresar un número de radicado.")

    if len(digitos) != LONGITUD:
        raise RadicadoInvalido(
            f"El radicado debe tener exactamente {LONGITUD} dígitos; "
            f"el que ingresó tiene {len(digitos)}."
        )

    anio = digitos[12:16]
    anio_actual = date.today().year
    if not (1990 <= int(anio) <= anio_actual + 1):
        raise RadicadoInvalido(
            f"El año del radicado ({anio}) no parece válido. "
            "Revise que los dígitos estén en el orden correcto."
        )

    return Radicado(
        completo=digitos,
        municipio_codigo=digitos[0:5],
        departamento_codigo=digitos[0:2],
        entidad_codigo=digitos[5:7],
        especialidad_codigo=digitos[7:9],
        despacho_numero=digitos[9:12],
        despacho_codigo=digitos[0:12],
        anio=anio,
        consecutivo=digitos[16:21],
        instancia=digitos[21:23],
    )
