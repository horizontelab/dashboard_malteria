"""Cuentas por cobrar (FACTURA Santander) y concentracion de clientes (VENTAS)."""
from collections import defaultdict

from google_sheets import conectar, leer_hoja
from resultado import ADMIN_ID, MESES, calcular, limpiar, numero, pesos
from productos import a_numero, detalle_ventas

COBRADO = {"SI", "SÍ", "S"}
PENDIENTE = {"NO", "", "ATENCION", "ATENCIÓN"}


def columna(encabezado, nombre, hoja):
    enc = [limpiar(h) for h in encabezado]
    for i, h in enumerate(enc):
        if h.startswith(limpiar(nombre)):
            return i
    raise KeyError(f"{hoja}: no encontre la columna '{nombre}'")


def cuentas_por_cobrar(filas):
    enc = filas[0]
    c_cli = columna(enc, "Cliente", "FACTURA Santander")
    c_imp = columna(enc, "Importe", "FACTURA Santander")
    c_cob = columna(enc, "Cobrado", "FACTURA Santander")

    pendiente, n_pend, ambiguas = defaultdict(float), 0, []
    for fila in filas[1:]:
        celda = lambda i: fila[i] if i < len(fila) else ""
        cliente, importe = str(celda(c_cli)).strip(), a_numero(celda(c_imp))
        if not cliente or importe <= 0:
            continue
        estado = limpiar(celda(c_cob))
        if estado in COBRADO:
            continue
        if estado in PENDIENTE:
            pendiente[cliente] += importe
            n_pend += 1
        else:
            ambiguas.append({"cliente": cliente, "importe": importe, "marca": str(celda(c_cob))})

    deudores = sorted(pendiente.items(), key=lambda x: -x[1])
    return {"total": sum(pendiente.values()), "facturas": n_pend,
            "deudores": [{"cliente": c, "monto": v} for c, v in deudores],
            "ambiguas": ambiguas}


def concentracion(detalle, top_n=3):
    """Suma por cliente todas las ventas (sin IVA) de los meses cargados."""
    por_cliente = defaultdict(float)
    for productos in detalle.values():
        for clientes in productos.values():
            for c in clientes:
                por_cliente[c["cliente"]] += c["total"]
    total = sum(por_cliente.values())
    ranking = sorted(por_cliente.items(), key=lambda x: -x[1])
    top = [{"cliente": c, "monto": v, "pct": v / total * 100} for c, v in ranking[:top_n]]
    return {"total": total, "clientes": len(por_cliente), "top": top,
            "pct_top": sum(t["pct"] for t in top)}


def calcular_cobranzas(meses_idx):
    sheets = conectar()
    cxc = cuentas_por_cobrar(leer_hoja(sheets, ADMIN_ID, "FACTURA Santander"))
    detalle = detalle_ventas(leer_hoja(sheets, ADMIN_ID, "VENTAS"), meses_idx)
    return cxc, concentracion(detalle)


if __name__ == "__main__":
    r = calcular()
    meses_idx = [MESES.index(m) for m in r["meses"]]
    cxc, conc = calcular_cobranzas(meses_idx)

    print("CUENTAS POR COBRAR")
    print(f"  Pendiente: {pesos(cxc['total'])} en {cxc['facturas']} facturas")
    for d in cxc["deudores"][:6]:
        print(f"    {d['cliente']:<35} {pesos(d['monto']):>12}")
    if cxc["ambiguas"]:
        tipos = sorted({a["marca"] for a in cxc["ambiguas"]})
        monto = sum(a["importe"] for a in cxc["ambiguas"])
        print(f"  Ambiguas (no contadas): {len(cxc['ambiguas'])} facturas por {pesos(monto)}")
        print(f"    marcadas como: {', '.join(tipos)}")

    print(f"\nCONCENTRACION DE CLIENTES ({r['meses'][0]}-{r['meses'][-1]})")
    print(f"  {conc['clientes']} clientes, {pesos(conc['total'])} vendidos")
    print(f"  Top {len(conc['top'])} = {numero(conc['pct_top'], 1)}% de las ventas:")
    for t in conc["top"]:
        print(f"    {t['cliente']:<35} {pesos(t['monto']):>12}  ({numero(t['pct'], 1)}%)")

    dif = conc["total"] - r["ventas"]
    print(f"\nControl: VENTAS {pesos(conc['total'])} vs RESULTADOS {pesos(r['ventas'])}"
          f"  -> diferencia {pesos(dif)} ({numero(dif / r['ventas'] * 100, 1)}%)")
