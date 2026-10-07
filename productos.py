"""Bloque 01 - Detalle: kilos por producto (VOLUMEN) y ventas por cliente (VENTAS)."""
from collections import defaultdict

from google_sheets import conectar, leer_hoja
from resultado import ADMIN_ID, MESES, calcular, indexar_filas, limpiar, numero, pesos, serie

MESES_LARGOS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
                "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

# En VOLUMEN, la seccion de Amola esta cargada en KILOS (no en unidades).
# Para esas marcas NO se multiplica por los kg por unidad.
MARCAS_EN_KILOS = {"AML"}


def mes_a_indice(texto):
    t = limpiar(texto)
    return MESES_LARGOS.index(t) if t in MESES_LARGOS else None


def a_numero(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except ValueError:
        return 0.0


def nombre_producto(p):
    return " ".join(str(p).split())


def volumen(filas):
    """Hoja VOLUMEN -> [{producto, marca, kg: [12 meses]}]."""
    col_mes = {}
    for i, h in enumerate(filas[0]):
        m = mes_a_indice(h)
        if m is not None and m not in col_mes:
            col_mes[m] = i

    productos, marca = [], None
    for fila in filas[1:]:
        if not fila or not str(fila[0]).strip():
            continue
        etiqueta = limpiar(fila[0])
        if "UNIDADES VENDIDAS" in etiqueta or "KILOS VENDIDOS" in etiqueta:
            marca = "OVQ" if ("OVQ" in etiqueta or "OVUNQUE" in etiqueta) else "AML"
            continue
        kg_unidad = fila[1] if len(fila) > 1 else None
        if marca is None or not isinstance(kg_unidad, (int, float)) or kg_unidad <= 0:
            continue
        factor = 1 if marca in MARCAS_EN_KILOS else kg_unidad
        kg = []
        for m in range(12):
            c = col_mes.get(m)
            valor = a_numero(fila[c]) if c is not None and c < len(fila) else 0
            kg.append(valor * factor)
        productos.append({"producto": nombre_producto(fila[0]), "marca": marca, "kg": kg})
    return productos


def detalle_ventas(filas, meses):
    """Hoja VENTAS -> {mes: {producto: [{cliente, cantidad, total}]}} ordenado por total."""
    encabezado = [limpiar(h) for h in filas[0]]

    def columna(nombre):
        for i, h in enumerate(encabezado):
            if h.startswith(limpiar(nombre)):
                return i
        raise KeyError(f"VENTAS: no encontre la columna '{nombre}'")

    c_mes, c_cli, c_prod = columna("MES"), columna("Cliente"), columna("Producto")
    c_cant, c_tot = columna("Cantidad"), columna("TOTAL con descuento")

    acum = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0])))
    for fila in filas[1:]:
        celda = lambda i: fila[i] if i < len(fila) else ""
        m = mes_a_indice(celda(c_mes))
        producto = celda(c_prod)
        if m not in meses or not str(producto).strip():
            continue
        cliente = str(celda(c_cli)).strip() or "Sin nombre"
        a = acum[MESES[m]][nombre_producto(producto)][cliente]
        a[0] += a_numero(celda(c_cant))
        a[1] += a_numero(celda(c_tot))

    salida = {}
    for mes, prods in acum.items():
        salida[mes] = {}
        for prod, clientes in prods.items():
            lista = [{"cliente": c, "cantidad": v[0], "total": round(v[1])} for c, v in clientes.items()]
            salida[mes][prod] = sorted(lista, key=lambda x: -x["total"])
    return salida


def calcular_productos(meses_idx):
    sheets = conectar()
    prods = volumen(leer_hoja(sheets, ADMIN_ID, "VOLUMEN"))

    for p in prods:
        p["kg_total"] = sum(p["kg"][i] for i in meses_idx)
    top10 = sorted(prods, key=lambda p: -p["kg_total"])[:10]

    por_mes = {}
    for i in meses_idx:
        items = [{"producto": p["producto"], "marca": p["marca"], "kg": p["kg"][i]}
                 for p in prods if p["kg"][i] > 0]
        por_mes[MESES[i]] = sorted(items, key=lambda x: -x["kg"])[:8]

    detalle = detalle_ventas(leer_hoja(sheets, ADMIN_ID, "VENTAS"), meses_idx)

    # kilos por marca segun VOLUMEN y segun RESULTADOS, para el control cruzado
    idx = indexar_filas(leer_hoja(sheets, ADMIN_ID, "RESULTADOS"))
    control = {}
    for marca, etiqueta in [("OVQ", "KILOS VENDIDOS OVUNQUE"), ("AML", "KILOS VENDIDOS AMOLA")]:
        res = serie(idx, etiqueta)
        control[marca] = [(sum(p["kg"][i] for p in prods if p["marca"] == marca), res[i])
                          for i in meses_idx]
    return {"todos": prods, "top10": top10, "por_mes": por_mes, "detalle": detalle,
            "control": control}


if __name__ == "__main__":
    r = calcular()
    meses_idx = [MESES.index(m) for m in r["meses"]]
    p = calcular_productos(meses_idx)

    print("Top 10 productos por kilos (acumulado del anio):")
    for i, prod in enumerate(p["top10"], 1):
        print(f"  {i:2}. [{prod['marca']}] {prod['producto']:<45} {numero(prod['kg_total'], 1):>9} kg")

    print("\nControl cruzado: kilos de VOLUMEN vs. RESULTADOS, por marca")
    for marca, filas in p["control"].items():
        print(f"  {marca}:")
        for mes, (kv, kr) in zip(r["meses"], filas):
            dif = kv - kr
            estado = "OK" if abs(dif) <= max(2, kr * 0.02) else f"DIFERENCIA de {numero(dif, 1)} kg"
            print(f"    {mes}: VOLUMEN {numero(kv, 1):>8} | RESULTADOS {numero(kr, 1):>8}  -> {estado}")

    ult = r["meses"][-1]
    print(f"\nProductos de {ult} y quien los compro:")
    for item in p["por_mes"][ult][:3]:
        print(f"  [{item['marca']}] {item['producto']} - {numero(item['kg'], 1)} kg")
        clientes = p["detalle"].get(ult, {}).get(item["producto"], [])
        if not clientes:
            print("      (sin detalle en la hoja VENTAS para este producto)")
        for c in clientes[:3]:
            print(f"      {c['cliente']}: {numero(c['cantidad'], 1)} u - {pesos(c['total'])}")
