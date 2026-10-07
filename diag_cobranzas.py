"""Que fuente sirve para cuentas por cobrar: FACTURA Santander vs MARGEN X VENTAS."""
from collections import Counter, defaultdict

from google_sheets import conectar, leer_hoja
from resultado import ADMIN_ID, limpiar, pesos
from productos import a_numero
from cobranzas import a_fecha, columna
from clientes import cliente_canonico

sheets = conectar()

# 1) Hasta cuando se uso FACTURA Santander
filas = leer_hoja(sheets, ADMIN_ID, "FACTURA Santander")
c_fec = columna(filas[0], "Fecha factura", "FACTURA Santander")
por_anio, ultima, sin_fecha = Counter(), None, 0
for fila in filas[1:]:
    f = a_fecha(fila[c_fec]) if c_fec < len(fila) else None
    if f:
        por_anio[f.year] += 1
        ultima = f if ultima is None or f > ultima else ultima
    elif any(str(v).strip() for v in fila):
        sin_fecha += 1
print("1) FACTURA Santander - facturas por anio (cobradas o no):")
for anio in sorted(por_anio):
    print(f"   {anio}: {por_anio[anio]}")
print(f"   Sin fecha: {sin_fecha}   |   Ultima factura: {ultima:%d/%m/%Y}\n")

# 2) Columna Cobrado de MARGEN X VENTAS
filas = leer_hoja(sheets, ADMIN_ID, "MARGEN X VENTAS")
enc = filas[0]
c_mes = columna(enc, "MES", "MARGEN X VENTAS")
c_cli = columna(enc, "Cliente", "MARGEN X VENTAS")
c_imp = columna(enc, "Ventas / FACTURACION", "MARGEN X VENTAS")
c_cob = columna(enc, "Cobrado", "MARGEN X VENTAS")

valores = defaultdict(lambda: [0, 0.0])
no_cobrado = defaultdict(float)
for fila in filas[1:]:
    celda = lambda i: fila[i] if i < len(fila) else ""
    cliente, importe = str(celda(c_cli)).strip(), a_numero(celda(c_imp))
    if not cliente or importe <= 0:
        continue
    estado = str(celda(c_cob)).strip()
    valores[estado][0] += 1
    valores[estado][1] += importe
    if limpiar(estado) not in {"SI", "SÍ"}:
        no_cobrado[(cliente_canonico(cliente), str(celda(c_mes)))] += importe

print("2) MARGEN X VENTAS - valores en la columna 'Cobrado':")
for estado, (n, v) in sorted(valores.items(), key=lambda x: -x[1][1]):
    print(f"   '{estado}': {n} ordenes, {pesos(v)}")

print("\n   Ordenes no marcadas como SI (cliente, mes):")
for (cliente, mes), v in sorted(no_cobrado.items(), key=lambda x: -x[1])[:15]:
    print(f"   {cliente[:30]:<30} {mes:<10} {pesos(v):>12}")
