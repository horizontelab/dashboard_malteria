"""Diagnostico de calidad de datos: facturas grandes, nombres de clientes y control VENTAS vs RESULTADOS."""
from collections import defaultdict
from datetime import date, timedelta

from google_sheets import conectar, leer_hoja
from resultado import ADMIN_ID, MESES, calcular, indexar_filas, limpiar, pesos, serie
from productos import a_numero, mes_a_indice
from cobranzas import COBRADO, columna


def fecha(v):
    """Las fechas llegan como numero de serie (ej. 46023) -> dd/mm/aaaa."""
    if isinstance(v, (int, float)) and 30000 < v < 80000:
        return (date(1899, 12, 30) + timedelta(days=int(v))).strftime("%d/%m/%Y")
    return str(v) if v not in ("", None) else "sin fecha"


sheets = conectar()
r = calcular()
meses_idx = [MESES.index(m) for m in r["meses"]]

# ---------------------------------------------------------------- 1
print("1) FACTURAS NO COBRADAS DE MAS DE $1.000.000 (FACTURA Santander)\n")
filas = leer_hoja(sheets, ADMIN_ID, "FACTURA Santander")
enc = filas[0]
c_fec = columna(enc, "Fecha factura", "FACTURA Santander")
c_cli = columna(enc, "Cliente", "FACTURA Santander")
c_imp = columna(enc, "Importe", "FACTURA Santander")
c_cob = columna(enc, "Cobrado", "FACTURA Santander")
for n, fila in enumerate(filas[1:], start=2):          # start=2: la fila 1 es el encabezado
    celda = lambda i: fila[i] if i < len(fila) else ""
    imp = a_numero(celda(c_imp))
    if imp > 1_000_000 and limpiar(celda(c_cob)) not in COBRADO:
        print(f"  fila {n:>4} | factura {celda(0)!s:<6} | {fecha(celda(c_fec)):<10} | "
              f"{str(celda(c_cli))[:28]:<28} | {pesos(imp):>13} | cobrado='{celda(c_cob)}'")

# ---------------------------------------------------------------- 2 y 3
filas = leer_hoja(sheets, ADMIN_ID, "VENTAS")
enc = filas[0]
c_mes, c_cli = columna(enc, "MES", "VENTAS"), columna(enc, "Cliente", "VENTAS")
c_uen = columna(enc, "UEN", "VENTAS")
c_bruto = columna(enc, "Total orden", "VENTAS")
c_neto = columna(enc, "TOTAL con descuento", "VENTAS")

por_cliente = defaultdict(float)
nombres = defaultdict(set)
por_mes = defaultdict(lambda: [0.0, 0.0])              # (mes, marca) -> [bruto, neto]
for fila in filas[1:]:
    celda = lambda i: fila[i] if i < len(fila) else ""
    m = mes_a_indice(celda(c_mes))
    if m not in meses_idx:
        continue
    cliente = str(celda(c_cli)).strip()
    neto = a_numero(celda(c_neto))
    por_cliente[cliente] += neto
    nombres[limpiar(cliente).split()[0] if cliente else ""].add(cliente)
    marca = "OVQ" if "OVUNQUE" in limpiar(celda(c_uen)) else "AML"
    por_mes[(m, marca)][0] += a_numero(celda(c_bruto))
    por_mes[(m, marca)][1] += neto

print("\n2) TOP 20 CLIENTES EN VENTAS (para detectar nombres duplicados)\n")
for c, v in sorted(por_cliente.items(), key=lambda x: -x[1])[:20]:
    print(f"  {c:<40} {pesos(v):>12}")

print("\n   Nombres que empiezan igual (posibles duplicados):")
for primera, variantes in sorted(nombres.items()):
    if len(variantes) > 1 and primera:
        print(f"   - {' | '.join(sorted(variantes))}")

print("\n3) VENTAS vs RESULTADOS por mes y marca\n")
idx = indexar_filas(leer_hoja(sheets, ADMIN_ID, "RESULTADOS"))
res = {"OVQ": serie(idx, "OVUNQUE", 1), "AML": serie(idx, "AMOLA", 1)}
print(f"  {'Mes':<4} {'Marca':<5} {'VENTAS bruto':>14} {'VENTAS c/desc':>14} {'RESULTADOS':>14}")
for m in meses_idx:
    for marca in ("OVQ", "AML"):
        bruto, neto = por_mes[(m, marca)]
        print(f"  {MESES[m]:<4} {marca:<5} {pesos(bruto):>14} {pesos(neto):>14} {pesos(res[marca][m]):>14}")
