"""Reposicion de clientes fabrica: que meses hizo pedido cada cerveceria."""
import re
import unicodedata
from datetime import date

from google_sheets import conectar, leer_varias, pestanias
from resultado import MESES, numero
from productos import MESES_LARGOS

FABRICAS = {
    "Almirante":       "1WLXv5fJrT00V9ySfve1nJV9vTcZIF22NCxwKQwJMCLA",
    "Sol de Invierno": "1bZCeIS-dRD0Tl0X-6KNSaiziFVFFSoafuWSRF-Shg10",
    "Cerveza Gringa":  "1TtKb0cx8sMkUCKfBDP2bLojAAsPZ6Xa50Lmk2XWTyII",
    "Gabriel Valdez":  "1thcttQWB7lc5_b3x5YF30l-H_6O1sSLFnFapX9DCgr0",
    "Straus":          "1CAYo51VAennTGpDGPVHYeHu46OiFXaQ8ecscUo80BxI",
}
# False: se evaluan los meses ya cerrados; el mes en curso se informa aparte
INCLUIR_MES_EN_CURSO = False

ABREV = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
         "AGO": 8, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12}


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def mes_desde_palabra(palabra):
    """'SEP' / 'Abril' / 'JUNIO' / 'Sept' / 'AGOST' -> numero de mes. 'envio' -> None."""
    t = sin_acentos(palabra).upper()
    if t in MESES_LARGOS:
        return MESES_LARGOS.index(t) + 1
    k = ABREV.get(t[:3])
    if k and (len(t) == 3 or MESES_LARGOS[k - 1].startswith(t)):
        return k
    return None


def periodo_de_pestania(nombre):
    """'SEP26' -> (2026, 9) | 'MAR26 Bis' -> (2026, 3) | 'NOV 25' -> (2025, 11) | 'Acuerdos' -> None."""
    for m in re.finditer(r"([A-Za-zÁÉÍÓÚáéíóúñÑ]{3,})[\s\-_/.']*(\d{4}|\d{2})(?!\d)", nombre):
        mes = mes_desde_palabra(m.group(1))
        if mes:
            anio = int(m.group(2))
            return (2000 + anio if anio < 100 else anio), mes
    return None


def a_cantidad(v):
    """Cantidad de bolsas: 38 o '38'. Precios ('$72,163'), 'SIN STOCK' o vacio -> None."""
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def es_total(fila):
    return bool(fila) and sin_acentos(str(fila[0])).upper().startswith("TOTAL")


def cantidad_pedido(filas):
    """(bolsas, kilos) de una pestania mensual."""
    # 1) fila de encabezados y columna de cantidades, buscando "Cantidad" en las primeras filas
    inicio, col = None, None
    for i, fila in enumerate(filas[:6]):
        cols = [j for j, v in enumerate(fila) if "CANTIDAD" in sin_acentos(str(v)).upper()]
        if cols:
            inicio, col = i + 1, cols[0]
            break

    # 2) sin encabezado "Cantidad" (caso Straus): la columna es la que tiene un numero
    #    chico (bolsas) en la fila TOTAL; el monto en pesos es grande
    if col is None:
        fila_total = next((f for f in filas if es_total(f)), [])
        candidatas = [j for j in range(1, min(5, len(fila_total)))
                      if a_cantidad(fila_total[j]) is not None and 0 <= a_cantidad(fila_total[j]) < 10000]
        col = candidatas[0] if candidatas else 1
        inicio = next((i + 1 for i, f in enumerate(filas[:6])
                       if f and "VARIEDAD" in sin_acentos(str(f[0])).upper()), 1)

    # 3) recorrer los productos desde el encabezado hasta la fila TOTAL
    total, suma, kilos = None, 0.0, 0.0
    for fila in filas[inicio:]:
        if not fila or not str(fila[0]).strip():
            continue
        cant = a_cantidad(fila[col]) if col < len(fila) else None
        if es_total(fila):
            total = cant              # si la fila TOTAL dice 0, el pedido vale 0
            break
        if cant and cant > 0:
            suma += cant
            m = re.search(r"(\d+([.,]\d+)?)\s*KG", sin_acentos(str(fila[0])).upper())
            if m:
                kilos += cant * float(m.group(1).replace(",", "."))
    return (total if total is not None else suma), kilos


def rangos(meses):
    """[2, 3, 4, 7] -> 'Feb-Abr, Jul'."""
    if not meses:
        return ""
    meses, partes = sorted(meses), []
    ini = ant = meses[0]
    for m in meses[1:] + [None]:
        if m is not None and m == ant + 1:
            ant = m
            continue
        partes.append(MESES[ini - 1] if ini == ant else f"{MESES[ini - 1]}-{MESES[ant - 1]}")
        if m is not None:
            ini = ant = m
    return ", ".join(partes)


def analizar_fabrica(sheets, sheet_id, anio, hasta, mes_hoy):
    del_anio = {}
    for t in pestanias(sheets, sheet_id):
        p = periodo_de_pestania(t)
        if p and p[0] == anio:
            del_anio.setdefault(p[1], []).append(t)       # 'MAR26' y 'MAR26 Bis' -> mismo mes
    datos = leer_varias(sheets, sheet_id, [t for ts in del_anio.values() for t in ts])

    con_pedido, vacias, kilos_mes, bolsas_mes = [], [], {}, {}
    for mes, tabs in del_anio.items():
        bolsas = kilos = 0.0
        for t in tabs:
            b, k = cantidad_pedido(datos[t])
            bolsas, kilos = bolsas + b, kilos + k
        (con_pedido if bolsas > 0 else vacias).append(mes)
        kilos_mes[mes], bolsas_mes[mes] = kilos, bolsas

    rango = range(1, hasta + 1)
    return {
        "activos": len([m for m in con_pedido if m in rango]),
        "total": len(rango),
        "sin_planilla": [m for m in rango if m not in del_anio],
        "vacias": [m for m in vacias if m in rango],
        "kilos_anio": sum(v for m, v in kilos_mes.items() if m in rango),
        "kilos_mes": kilos_mes,
        "bolsas_mes": bolsas_mes,
        "mes_en_curso": None if INCLUIR_MES_EN_CURSO else (mes_hoy in con_pedido),
    }


def calcular_fabricas(hoy=None):
    hoy = hoy or date.today()
    hasta = hoy.month if INCLUIR_MES_EN_CURSO else max(hoy.month - 1, 1)
    sheets = conectar()
    resultados = {}
    for nombre, sheet_id in FABRICAS.items():
        try:      # si una planilla falla (ej. sin permiso), las demas siguen
            resultados[nombre] = analizar_fabrica(sheets, sheet_id, hoy.year, hasta, hoy.month)
        except Exception as e:
            resultados[nombre] = {"error": str(e)[:150]}
    return resultados, hasta, hoy


if __name__ == "__main__":
    res, hasta, hoy = calcular_fabricas()
    print(f"REPOSICION FABRICAS - {hoy.year}, meses evaluados: Ene-{MESES[hasta - 1]} ({hasta} meses)\n")
    for nombre, r in sorted(res.items(), key=lambda x: -x[1].get("activos", -1)):
        if "error" in r:
            print(f"  {nombre:<16} ERROR: {r['error']}\n")
            continue
        pct = r["activos"] / r["total"] * 100
        print(f"  {nombre:<16} {r['activos']}/{r['total']} meses con pedido ({pct:.0f}%)  "
              f"- {numero(r['kilos_anio'])} kg en el anio")
        detalle = [f"{MESES[m - 1]}: {numero(r['bolsas_mes'][m])} bolsas / {numero(r['kilos_mes'][m])} kg"
                   for m in sorted(r["bolsas_mes"]) if r["bolsas_mes"][m] > 0]
        print(f"      Pedidos: {' | '.join(detalle) or 'ninguno'}")
        faltan = []
        if r["sin_planilla"]:
            faltan.append(f"{rangos(r['sin_planilla'])} (sin planilla)")
        if r["vacias"]:
            faltan.append(f"{rangos(r['vacias'])} (planilla vacia)")
        print(f"      Sin pedido: {' - '.join(faltan) or 'ninguno'}")
        if r["mes_en_curso"] is not None:
            print(f"      {MESES[hoy.month - 1]} (en curso): {'ya pidio' if r['mes_en_curso'] else 'todavia no pidio'}")
        print()
