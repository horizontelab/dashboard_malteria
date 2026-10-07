"""Stock Amola, deuda con proveedor de mijo y sueldos de socias."""
import re
from collections import defaultdict
from datetime import date

from google_sheets import conectar, leer_hoja, pestanias
from resultado import MESES, limpiar, numero, pesos
from productos import a_numero, mes_a_indice
from cobranzas import a_fecha, columna

STOCK_ID = "1cHWR8wgxRukq6lSNfErv3ObKdWBv8i-K1potY3IGLm0"
GRANOS_ID = "1DUquxvau4pTL6Non4GdWH_bhuhVhPa92F_PF4N7zz8M"
TAREAS_ID = "16vsJdXxio2Aqc0WrGypaw8g0R6izQta3kZAe4VzZytg"


# ------------------------------------------------------------------ Stock Amola
def stock_amola(filas):
    enc = filas[0]
    c_prod, c_kg = columna(enc, "Producto", "STOCK"), columna(enc, "Kilos Totales", "STOCK")
    items = []
    for fila in filas[1:]:
        producto = fila[c_prod] if c_prod < len(fila) else ""
        if not str(producto).strip():
            break                          # la tabla termina en la primera fila sin producto
        kg = a_numero(fila[c_kg]) if c_kg < len(fila) else 0.0
        items.append({"producto": str(producto).strip(), "kg": kg})

    fecha_control = None                   # la fecha esta en la celda debajo de "Fecha control"
    for i, fila in enumerate(filas[:-1]):
        for j, v in enumerate(fila):
            if limpiar(v) == "FECHA CONTROL" and j < len(filas[i + 1]):
                fecha_control = a_fecha(filas[i + 1][j])
    return {"items": sorted(items, key=lambda x: -x["kg"]),
            "total": sum(x["kg"] for x in items), "fecha_control": fecha_control}


# ------------------------------------------------------------------ Deuda mijo
def deuda_mijo(sheets):
    hoja = pestanias(sheets, GRANOS_ID)[0]            # la primera pestania es la mas reciente
    filas = leer_hoja(sheets, GRANOS_ID, hoja)
    saldo = None
    for fila in filas:
        for j, v in enumerate(fila):
            if limpiar(v) == "SALDO":                  # exacto: "SALDO MIJO" es en kilos, no en pesos
                saldo = next((w for w in fila[j + 1:] if isinstance(w, (int, float))), None)
                break
        if saldo is not None:
            break
    anios = [int(a) if len(a) == 4 else 2000 + int(a) for a in re.findall(r"\d{4}|\d{2}", hoja)]
    return {"saldo": saldo, "hoja": hoja, "anio": max(anios) if anios else None}


# ------------------------------------------------------------------ Sueldos socias
SECCIONES = {"OVQ", "AML", "TOTAL", "PAGADO"}


def sueldos(filas, anio):
    """Bloque del anio en 'Sueldo Asignado': secciones OVQ | AML | TOTAL | PAGADO, cada una
    con columnas 'Sofi $', 'Ro $', 'Dbo $'. Se lee cada seccion por separado."""
    inicio = next((i for i, f in enumerate(filas)
                   if f and a_numero(f[0]) == anio and len([v for v in f if str(v).strip()]) == 1), None)
    if inicio is None:
        raise ValueError(f"'Sueldo Asignado' no tiene bloque {anio}")
    enc = filas[inicio + 1]

    # donde empieza cada seccion y que columnas $ tiene
    inicios = sorted((j, limpiar(v)) for j, v in enumerate(enc) if limpiar(v) in SECCIONES)
    columnas = {}
    for k, (j, nombre) in enumerate(inicios):
        fin = inicios[k + 1][0] if k + 1 < len(inicios) else len(enc)
        columnas[nombre] = [(c, str(enc[c]).replace("$", "").strip())
                            for c in range(j, fin) if str(enc[c]).strip().endswith("$")]

    acum = {s: defaultdict(float) for s in columnas}
    meses_asignados = []
    for fila in filas[inicio + 2:]:
        m = mes_a_indice(fila[0]) if fila else None
        if m is None:
            break
        for seccion, cols in columnas.items():
            for c, socia in cols:
                acum[seccion][socia] += a_numero(fila[c]) if c < len(fila) else 0.0
        fuente = columnas.get("TOTAL") or columnas.get("OVQ", []) + columnas.get("AML", [])
        if sum(a_numero(fila[c]) for c, _ in fuente if c < len(fila)) > 0:
            meses_asignados.append(m)

    if "TOTAL" in acum:
        asignado = dict(acum["TOTAL"])
    else:
        asignado = defaultdict(float)
        for s in ("OVQ", "AML"):
            for socia, v in acum.get(s, {}).items():
                asignado[socia] += v
    pagado = dict(acum.get("PAGADO", {}))
    return {"asignado": dict(asignado), "pagado": pagado, "meses": meses_asignados,
            "total_asignado": sum(asignado.values()), "total_pagado": sum(pagado.values())}


def calcular_varios(hoy=None):
    hoy = hoy or date.today()
    sheets = conectar()
    salida = {}
    tareas = [("stock", lambda: stock_amola(leer_hoja(sheets, STOCK_ID, "STOCK"))),
              ("mijo", lambda: deuda_mijo(sheets)),
              ("sueldos", lambda: sueldos(leer_hoja(sheets, TAREAS_ID, "Sueldo Asignado"), hoy.year))]
    for nombre, fn in tareas:
        try:
            salida[nombre] = fn()
        except Exception as e:
            salida[nombre] = {"error": str(e)[:200]}
    return salida


if __name__ == "__main__":
    hoy = date.today()
    r = calcular_varios(hoy)

    print("STOCK AMOLA")
    s = r["stock"]
    if "error" in s:
        print(f"  ERROR: {s['error']}")
    else:
        print(f"  Total: {numero(s['total'], 1)} kg | ultimo control fisico: "
              f"{s['fecha_control']:%d/%m/%Y}" if s["fecha_control"] else "  (sin fecha de control)")
        for it in s["items"]:
            print(f"    {it['producto']:<42} {numero(it['kg'], 1):>7} kg")

    print("\nDEUDA PROVEEDOR MIJO (Castro)")
    mj = r["mijo"]
    if "error" in mj:
        print(f"  ERROR: {mj['error']}")
    else:
        aviso = "  <- planilla DESACTUALIZADA" if mj["anio"] and mj["anio"] < hoy.year - 1 else ""
        print(f"  Saldo: {pesos(mj['saldo']) if mj['saldo'] is not None else 'no encontrado'} "
              f"(pestania '{mj['hoja']}'){aviso}")

    print(f"\nSUELDOS SOCIAS {hoy.year}")
    su = r["sueldos"]
    if "error" in su:
        print(f"  ERROR: {su['error']}")
    else:
        meses = f"{MESES[su['meses'][0]]}-{MESES[su['meses'][-1]]}" if su["meses"] else "-"
        print(f"  Asignado {meses}: {pesos(su['total_asignado'])}  |  Pagado: {pesos(su['total_pagado'])}  |  "
              f"Diferencia: {pesos(su['total_asignado'] - su['total_pagado'])}")
        for socia, v in su["asignado"].items():
            pag = su["pagado"].get(socia, 0)
            print(f"    {socia:<8} asignado {pesos(v):>11}   pagado {pesos(pag):>11}   pendiente {pesos(v - pag):>11}")
