"""Catálogos oficiales usados para interpretar el Código Único de Radicación.

Los mapas son deliberadamente conservadores: solo se incluyen códigos de los que
se tiene certeza razonable. Cuando un código no está en el catálogo la aplicación
muestra el código crudo en vez de inventar una descripción, para no dar
información equivocada al usuario.
"""

# Posiciones 1-2 del radicado: código DANE de departamento.
DEPARTAMENTOS = {
    "05": "ANTIOQUIA",
    "08": "ATLÁNTICO",
    "11": "BOGOTÁ D.C.",
    "13": "BOLÍVAR",
    "15": "BOYACÁ",
    "17": "CALDAS",
    "18": "CAQUETÁ",
    "19": "CAUCA",
    "20": "CESAR",
    "23": "CÓRDOBA",
    "25": "CUNDINAMARCA",
    "27": "CHOCÓ",
    "41": "HUILA",
    "44": "LA GUAJIRA",
    "47": "MAGDALENA",
    "50": "META",
    "52": "NARIÑO",
    "54": "NORTE DE SANTANDER",
    "63": "QUINDÍO",
    "66": "RISARALDA",
    "68": "SANTANDER",
    "70": "SUCRE",
    "73": "TOLIMA",
    "76": "VALLE DEL CAUCA",
    "81": "ARAUCA",
    "85": "CASANARE",
    "86": "PUTUMAYO",
    "88": "ARCHIPIÉLAGO DE SAN ANDRÉS",
    "91": "AMAZONAS",
    "94": "GUAINÍA",
    "95": "GUAVIARE",
    "97": "VAUPÉS",
    "99": "VICHADA",
}

# Posiciones 1-5 del radicado: código DANE de municipio.
# Se incluyen las capitales de departamento y los municipios del Área
# Metropolitana Centro Occidente (Risaralda), que es donde se concentran
# la mayoría de los procesos consultados. Los municipios no listados se
# muestran por su código.
MUNICIPIOS = {
    # Capitales de departamento
    "05001": "MEDELLÍN",
    "08001": "BARRANQUILLA",
    "11001": "BOGOTÁ D.C.",
    "13001": "CARTAGENA",
    "15001": "TUNJA",
    "17001": "MANIZALES",
    "18001": "FLORENCIA",
    "19001": "POPAYÁN",
    "20001": "VALLEDUPAR",
    "23001": "MONTERÍA",
    "25286": "FUNZA",
    "25754": "SOACHA",
    "27001": "QUIBDÓ",
    "41001": "NEIVA",
    "44001": "RIOHACHA",
    "47001": "SANTA MARTA",
    "50001": "VILLAVICENCIO",
    "52001": "PASTO",
    "54001": "CÚCUTA",
    "63001": "ARMENIA",
    "66001": "PEREIRA",
    "68001": "BUCARAMANGA",
    "70001": "SINCELEJO",
    "73001": "IBAGUÉ",
    "76001": "CALI",
    "81001": "ARAUCA",
    "85001": "YOPAL",
    "86001": "MOCOA",
    "88001": "SAN ANDRÉS",
    "91001": "LETICIA",
    "94001": "INÍRIDA",
    "95001": "SAN JOSÉ DEL GUAVIARE",
    "97001": "MITÚ",
    "99001": "PUERTO CARREÑO",
    # Risaralda (residencia habitual del usuario)
    "66045": "APÍA",
    "66075": "BALBOA",
    "66088": "BELÉN DE UMBRÍA",
    "66170": "DOSQUEBRADAS",
    "66318": "GUÁTICA",
    "66383": "LA CELIA",
    "66400": "LA VIRGINIA",
    "66440": "MARSELLA",
    "66456": "MISTRATÓ",
    "66572": "PUEBLO RICO",
    "66594": "QUINCHÍA",
    "66682": "SANTA ROSA DE CABAL",
    "66687": "SANTUARIO",
    # Otros municipios frecuentes
    "05266": "ENVIGADO",
    "05360": "ITAGÜÍ",
    "05631": "SABANETA",
    "05088": "BELLO",
    "76109": "BUENAVENTURA",
    "76520": "PALMIRA",
    "76834": "TULUÁ",
    "17380": "LA DORADA",
    "73268": "ESPINAL",
    "68276": "FLORIDABLANCA",
    "08758": "SOLEDAD",
}

# Posiciones 6-7: tipo de entidad / corporación.
ENTIDADES = {
    "10": "CORTE SUPREMA DE JUSTICIA",
    "11": "CONSEJO SUPERIOR DE LA JUDICATURA",
    "12": "CONSEJO SECCIONAL DE LA JUDICATURA",
    "13": "COMISIÓN NACIONAL DE DISCIPLINA JUDICIAL",
    "22": "TRIBUNAL SUPERIOR DE DISTRITO JUDICIAL",
    "23": "TRIBUNAL ADMINISTRATIVO",
    "31": "JUZGADO DE CIRCUITO",
    "33": "JUZGADO ADMINISTRATIVO",
    "40": "JUZGADO MUNICIPAL",
    "41": "JUZGADO MUNICIPAL DE PEQUEÑAS CAUSAS",
}

# Posiciones 8-9: especialidad del despacho.
# Catálogo parcial: solo las especialidades de uso más frecuente y verificable.
ESPECIALIDADES = {
    "03": "CIVIL",
    "04": "LABORAL",
    "05": "FAMILIA",
}


def nombre_departamento(codigo: str) -> str:
    return DEPARTAMENTOS.get(codigo, f"Departamento {codigo}")


def nombre_municipio(codigo: str) -> str:
    return MUNICIPIOS.get(codigo, f"Municipio {codigo}")


def nombre_entidad(codigo: str) -> str:
    return ENTIDADES.get(codigo, f"Entidad {codigo}")


def nombre_especialidad(codigo: str) -> str:
    return ESPECIALIDADES.get(codigo, f"Especialidad {codigo}")
