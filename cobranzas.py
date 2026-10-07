"""Cuentas por cobrar 2026 (MARGEN X VENTAS), historico (FACTURA Santander) y concentracion (VENTAS)."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from google_sheets import conectar, leer_hoja
from resultado import ADMIN_ID, MESES, calcular, limpiar, numero, pesos
from productos import a_numero, mes_a_indice
from clientes import cliente_canonico

COBRADO = {"SI", "SÍ", "S"}
ATENCION = {"ATENCION", "ATENCIÓN"}


def columna(encabezado, nombre, hoja):
    enc = [limpiar(h) for h in encabezado]
    for i, h in enumerate(enc):
        if h.startswith(limpiar(nombre)):
            return i
    raise KeyError(f"{hoja}: no encontre la columna '{nombre}'")


def a_fecha(v):
    """Numero de serie de Sheets (46023) o texto dd/mm/aaaa -> date. Si no se puede, None."""
    if isinstance(v, (int, float)) and 30000 < v < 80000:
        return date(1899, 12, 30) + timedelta(days=int(v))
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            pass
    return None


def cuentas_por_cobrar(filas, hoy):
    """MARGEN X VENTAS: una fila por orden. Todo lo que no dice SI en 'Cobrado' es por cobrar."""
    hoja = "MARGEN X VENTAS"
    enc = filas[0]
    c_mes, c_cli = columna(enc, "MES", hoja), columna(enc, "Cliente", hoja)
    c_imp, c_cob = columna(enc, "Ventas / FACTURACION", hoja), columna(enc, "Cobrado", hoja)

    pendientes, ambiguas = [], []
    for n, fila in enumerate(filas[1:], start=2):
        celda = lambda i: fila[i] if i < len(fila) else ""
        cliente, importe = str(celda(c_cli)).strip(), a_numero(celda(c_imp))
        if not cliente or importe <= 0:
            continue
        crudo = str(celda(c_cob)).strip()
        estado = limpiar(crudo)
        if estado in COBRADO:
            continue
        m = mes_a_indice(celda(c_mes))
        item = {"fila": n, "cliente": cliente_canonico(cliente), "importe": importe,
                "mes": MESES[m] if m is not None else "?",
                # la planilla es del anio en curso: atraso = meses entre la venta y hoy
                "meses_atraso": (hoy.month - 1 - m) if m is not None else None}
        if estado == "NO":
            item["estado"] = "No cobrado"
        elif estado == "":
            item["estado"] = "Sin marcar"
        elif estado in ATENCION:
            item["estado"] = "Atencion"
        else:
            item["estado"], item["marca"] = "Ambigua", crudo
            ambiguas.append(item)
            continue
        pendientes.append(item)

    por_cliente, por_estado = defaultdict(float), defaultdict(lambda: [0, 0.0])
    for p in pendientes:
        por_cliente[p["cliente"]] += p["importe"]
        por_estado[p["estado"]][0] += 1
        por_estado[p["estado"]][1] += p["importe"]
    return {"total": sum(p["importe"] for p in pendientes), "ordenes": len(pendientes),
            "por_estado": dict(por_estado),
            "deudores": sorted(([c, v] for c, v in por_cliente.items()), key=lambda x: -x[1]),
            "pendientes": sorted(pendientes, key=lambda p: -p["importe"]), "ambiguas": ambiguas}


def historico_santander(filas):
    """FACTURA Santander (se uso hasta 2024): facturas que nunca se marcaron como cobradas."""
    hoja = "FACTURA Santander"
    enc = filas[0]
    c_fec, c_cli = columna(enc, "Fecha factura", hoja), columna(enc, "Cliente", hoja)
    c_imp, c_cob = columna(enc, "Importe", hoja), columna(enc, "Cobrado", hoja)
    pendientes, ultima = [], None
    for n, fila in enumerate(filas[1:], start=2):
        celda = lambda i: fila[i] if i < len(fila) else ""
        f = a_fecha(celda(c_fec))
        if f:
            ultima = f if ultima is None or f > ultima else ultima
        cliente, importe = str(celda(c_cli)).strip(), a_numero(celda(c_imp))
        if cliente and importe > 0 and limpiar(celda(c_cob)) in {"NO", ""} | ATENCION:
            pendientes.append({"fila": n, "factura": celda(0), "fecha": f,
                               "cliente": cliente_canonico(cliente), "importe": importe})
    return {"total": sum(p["importe"] for p in pendientes), "facturas": len(pendientes),
            "ultima_factura": ultima, "pendientes": sorted(pendientes, key=lambda p: -p["importe"])}


def concentracion(filas, meses_idx, top_n=3):
    """Ventas BRUTAS ('Total orden', la misma base que RESULTADOS) por cliente unificado."""
    enc = filas[0]
    c_mes = columna(enc, "MES", "VENTAS")
    c_cli = columna(enc, "Cliente", "VENTAS")
    c_bruto = columna(enc, "Total orden", "VENTAS")
    por_cliente = defaultdict(float)
    for fila in filas[1:]:
        celda = lambda i: fila[i] if i < len(fila) else ""
        if mes_a_indice(celda(c_mes)) in meses_idx and str(celda(c_cli)).strip():
            por_cliente[cliente_canonico(celda(c_cli))] += a_numero(celda(c_bruto))
    total = sum(por_cliente.values())
    ranking = [{"cliente": c, "monto": v, "pct": v / total * 100}
               for c, v in sorted(por_cliente.items(), key=lambda x: -x[1])]
    return {"total": total, "clientes": len(ranking), "ranking": ranking,
            "pct_top": sum(r["pct"] for r in ranking[:top_n]), "top_n": top_n}


def calcular_cobranzas(meses_idx, hoy=None):
    hoy = hoy or date.today()
    sheets = conectar()
    cxc = cuentas_por_cobrar(leer_hoja(sheets, ADMIN_ID, "MARGEN X VENTAS"), hoy)
    hist = historico_santander(leer_hoja(sheets, ADMIN_ID, "FACTURA Santander"))
    conc = concentracion(leer_hoja(sheets, ADMIN_ID, "VENTAS"), meses_idx)
    return cxc, hist, conc


if __name__ == "__main__":
    r = calcular()
    meses_idx = [MESES.index(m) for m in r["meses"]]
    cxc, hist, conc = calcular_cobranzas(meses_idx)

    print("CUENTAS POR COBRAR 2026 (MARGEN X VENTAS, montos con IVA)")
    print(f"  Total: {pesos(cxc['total'])} en {cxc['ordenes']} ordenes")
    for estado, (n, v) in cxc["por_estado"].items():
        print(f"    {estado:<12} {n:>3} ordenes  {pesos(v):>12}")
    print("\n  Por cliente:")
    for c, v in cxc["deudores"][:8]:
        print(f"    {c:<35} {pesos(v):>12}")
    print("\n  Ordenes mas grandes:")
    for p in cxc["pendientes"][:6]:
        atraso = f"{p['meses_atraso']} meses" if p["meses_atraso"] is not None else "?"
        print(f"    fila {p['fila']:>4} | {p['mes']:<4} ({atraso:>8}) | {p['cliente'][:28]:<28} | "
              f"{pesos(p['importe']):>12} | {p['estado']}")
    if cxc["ambiguas"]:
        print(f"\n  Ambiguas: {len(cxc['ambiguas'])} ordenes, marcadas como: "
              f"{', '.join(sorted({a['marca'] for a in cxc['ambiguas']}))}")

    print(f"\nHISTORICO A DEPURAR (FACTURA Santander, ultima factura {hist['ultima_factura']:%d/%m/%Y})")
    print(f"  {hist['facturas']} facturas nunca marcadas como cobradas: {pesos(hist['total'])}")

    print(f"\nCONCENTRACION DE CLIENTES ({r['meses'][0]}-{r['meses'][-1]}, ventas brutas)")
    print(f"  {conc['clientes']} clientes, {pesos(conc['total'])} | "
          f"Top {conc['top_n']} = {numero(conc['pct_top'], 1)}%")
    for x in conc["ranking"][:5]:
        print(f"    {x['cliente']:<35} {pesos(x['monto']):>12}  ({numero(x['pct'], 1)}%)")
