"""Cuentas por cobrar (FACTURA Santander) y concentracion de clientes (VENTAS)."""
from collections import defaultdict
from datetime import date, datetime, timedelta

from google_sheets import conectar, leer_hoja
from resultado import ADMIN_ID, MESES, calcular, limpiar, numero, pesos
from productos import a_numero, mes_a_indice
from clientes import cliente_canonico

COBRADO = {"SI", "SÍ", "S"}
PENDIENTE = {"NO", "", "ATENCION", "ATENCIÓN"}
VIGENTE_DIAS = 365                     # mas viejo que esto = "a revisar", no cuenta como pendiente


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


def tramo(f, hoy):
    if f is None:
        return "Sin fecha"
    dias = (hoy - f).days
    if dias <= 90:
        return "Hasta 90 dias"
    if dias <= VIGENTE_DIAS:
        return "91 a 365 dias"
    return "Mas de 1 anio"


def cuentas_por_cobrar(filas, hoy):
    enc = filas[0]
    c_fec = columna(enc, "Fecha factura", "FACTURA Santander")
    c_cli = columna(enc, "Cliente", "FACTURA Santander")
    c_imp = columna(enc, "Importe", "FACTURA Santander")
    c_cob = columna(enc, "Cobrado", "FACTURA Santander")

    pendientes, ambiguas = [], []
    for n, fila in enumerate(filas[1:], start=2):
        celda = lambda i: fila[i] if i < len(fila) else ""
        cliente, importe = str(celda(c_cli)).strip(), a_numero(celda(c_imp))
        if not cliente or importe <= 0:
            continue
        estado = limpiar(celda(c_cob))
        if estado in COBRADO:
            continue
        f = a_fecha(celda(c_fec))
        item = {"fila": n, "factura": celda(0), "fecha": f, "cliente": cliente_canonico(cliente),
                "importe": importe, "tramo": tramo(f, hoy)}
        if estado in PENDIENTE:
            pendientes.append(item)
        else:
            item["marca"] = str(celda(c_cob))
            ambiguas.append(item)

    por_tramo = defaultdict(lambda: [0, 0.0])
    for p in pendientes:
        por_tramo[p["tramo"]][0] += 1
        por_tramo[p["tramo"]][1] += p["importe"]

    vigentes = [p for p in pendientes if p["tramo"] not in ("Mas de 1 anio",)]
    viejas = [p for p in pendientes if p["tramo"] == "Mas de 1 anio"]
    deudores = defaultdict(float)
    for p in vigentes:
        deudores[p["cliente"]] += p["importe"]

    return {"total_vigente": sum(p["importe"] for p in vigentes), "facturas_vigentes": len(vigentes),
            "deudores": sorted(([c, v] for c, v in deudores.items()), key=lambda x: -x[1]),
            "por_tramo": dict(por_tramo), "viejas": viejas, "ambiguas": ambiguas}


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
    cxc = cuentas_por_cobrar(leer_hoja(sheets, ADMIN_ID, "FACTURA Santander"), hoy)
    conc = concentracion(leer_hoja(sheets, ADMIN_ID, "VENTAS"), meses_idx)
    return cxc, conc


if __name__ == "__main__":
    r = calcular()
    meses_idx = [MESES.index(m) for m in r["meses"]]
    cxc, conc = calcular_cobranzas(meses_idx)

    print("CUENTAS POR COBRAR - por antiguedad")
    for t in ["Hasta 90 dias", "91 a 365 dias", "Mas de 1 anio", "Sin fecha"]:
        if t in cxc["por_tramo"]:
            n, v = cxc["por_tramo"][t]
            print(f"  {t:<15} {n:>3} facturas  {pesos(v):>14}")

    print(f"\n  Pendiente vigente (ultimo anio): {pesos(cxc['total_vigente'])} en {cxc['facturas_vigentes']} facturas")
    for c, v in cxc["deudores"][:6]:
        print(f"    {c:<35} {pesos(v):>12}")

    if cxc["viejas"]:
        print(f"\n  A REVISAR - sin cobrar hace mas de 1 anio ({len(cxc['viejas'])} facturas):")
        for p in sorted(cxc["viejas"], key=lambda x: -x["importe"])[:10]:
            print(f"    fila {p['fila']:>4} | factura {p['factura']!s:<5} | {p['fecha']:%d/%m/%Y} | "
                  f"{p['cliente'][:25]:<25} | {pesos(p['importe']):>12}")

    if cxc["ambiguas"]:
        print(f"\n  Ambiguas (no contadas): {len(cxc['ambiguas'])} facturas por "
              f"{pesos(sum(a['importe'] for a in cxc['ambiguas']))}")

    print(f"\nCONCENTRACION DE CLIENTES ({r['meses'][0]}-{r['meses'][-1]}, ventas brutas)")
    print(f"  {conc['clientes']} clientes, {pesos(conc['total'])}")
    print(f"  Top {conc['top_n']} = {numero(conc['pct_top'], 1)}% de las ventas")
    for x in conc["ranking"][:6]:
        print(f"    {x['cliente']:<35} {pesos(x['monto']):>12}  ({numero(x['pct'], 1)}%)")
