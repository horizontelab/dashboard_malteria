"""Bloque 01 - Margenes de referencia por producto (planilla COSTOS y Precios)."""
import re

from google_sheets import conectar, leer_hoja
from resultado import MESES, calcular, limpiar, numero, pesos
from productos import calcular_productos, mes_a_indice

COSTOS_ID = "1n-zUklqxqn8elCfrEyn94AGy7tSl7Z2BLVvQmSEePI0"
HOJA_OVQ = "MARGEN "            # ojo: el nombre real de la pestania tiene un espacio al final
HOJA_AML = "AML MARGEN"
# Si el margen OVQ da negativo y el nombre contiene esto, es el problema del costo recalculado
COSTO_RECALCULADO = ["SARRACENO"]


def sin_tamanio(nombre):
    """'Harina de Mijo Germinado 10 Kg' -> 'HARINA DE MIJO GERMINADO'."""
    return re.sub(r"\s+\d+([.,]\d+)?\s*(KG|G|GR)?$", "", limpiar(nombre)).strip()


def margenes_ovq(filas, mes_ref):
    """Hoja 'MARGEN ' -> {'MIJO PALE ALE E 15': {'pct': 23.1, 'mes': 'Jun'}}."""
    inicio = {}                                   # mes -> columna donde arranca su bloque
    for c, h in enumerate(filas[0]):
        m = mes_a_indice(h)
        if m is not None:
            inicio[m] = c                         # ultima aparicion (DICIEMBRE del anio anterior queda pisado)
    sub = [limpiar(x) for x in filas[1]] if len(filas) > 1 else []

    def col_pct(m):
        c = inicio[m]
        for j in range(c, min(c + 6, len(sub))):
            if sub[j] == "%":
                return j
        return None

    # primero el mes de referencia; si esta vacio, el mes anterior con dato
    orden = [mes_ref] + sorted([m for m in inicio if m < mes_ref], reverse=True)
    salida, nombre = {}, ""
    for fila in filas[2:]:
        if fila and str(fila[0]).strip():
            nombre = fila[0]                      # el nombre aparece solo en la primera fila del producto
        if len(fila) < 3 or not nombre:
            continue
        cat, peso = fila[1], fila[2]
        if not str(cat).strip() or not isinstance(peso, (int, float)):
            continue
        clave = limpiar(f"{nombre} {cat} {peso:g}")
        for m in orden:
            if m not in inicio:
                continue
            c = col_pct(m)
            if c is not None and c < len(fila) and isinstance(fila[c], (int, float)):
                salida[clave] = {"pct": fila[c] * 100, "mes": MESES[m]}
                break
    return salida


def margenes_aml(filas, mes_ref):
    """Hoja 'AML MARGEN' -> ({'HARINA DE MIJO GERMINADO': {'DIST': 5874, ...}}, 'Jun')."""
    bloques, mes, canales = {}, None, None
    for fila in filas:
        no_vacias = [v for v in fila if str(v).strip()]
        if not no_vacias:
            continue
        if len(no_vacias) == 1 and mes_a_indice(fila[0]) is not None:   # fila con solo el mes
            mes, canales = mes_a_indice(fila[0]), None
            bloques[mes] = {}
            continue
        if mes is None:
            continue
        if "MARGEN" in limpiar(fila[0]):                                # encabezado de canales
            canales = [str(v).strip() for v in fila[1:]]
            continue
        if canales and str(fila[0]).strip():
            valores = {}
            for i, canal in enumerate(canales):
                if canal and i + 1 < len(fila) and isinstance(fila[i + 1], (int, float)):
                    valores[canal] = fila[i + 1]
            if valores:
                bloques[mes][limpiar(fila[0])] = valores
    con_datos = [m for m, v in bloques.items() if v]
    if not con_datos:
        return {}, None
    m = mes_ref if bloques.get(mes_ref) else max(con_datos)
    return bloques[m], MESES[m]


def asignar_margenes(productos, m_ovq, m_aml):
    """Agrega a cada producto su texto de margen (OVQ) o sus margenes por canal (AML)."""
    sin_match = []
    for p in productos:
        nombre = limpiar(p["producto"])
        if p["marca"] == "OVQ":
            m = m_ovq.get(nombre)
            if m is None:
                p["margen_txt"], p["margen_estado"] = "sin margen en COSTOS", "falta"
                sin_match.append(p["producto"])
            elif m["pct"] < 0 and any(x in nombre for x in COSTO_RECALCULADO):
                p["margen_txt"], p["margen_estado"] = "dato no confiable", "no_confiable"
            elif m["pct"] < 0:
                p["margen_txt"], p["margen_estado"] = f"{numero(m['pct'], 1)}% - REVISAR", "negativo"
            else:
                p["margen_txt"], p["margen_estado"] = f"{numero(m['pct'], 1)}% neto", "ok"
        else:
            canales = m_aml.get(sin_tamanio(p["producto"]))
            p["canales"] = canales
            if canales is None:
                sin_match.append(p["producto"])
    return sin_match


def calcular_margenes(mes_ref):
    sheets = conectar()
    m_ovq = margenes_ovq(leer_hoja(sheets, COSTOS_ID, HOJA_OVQ), mes_ref)
    m_aml, mes_aml = margenes_aml(leer_hoja(sheets, COSTOS_ID, HOJA_AML), mes_ref)
    return m_ovq, m_aml, mes_aml


if __name__ == "__main__":
    r = calcular()
    meses_idx = [MESES.index(m) for m in r["meses"]]
    p = calcular_productos(meses_idx)
    m_ovq, m_aml, mes_aml = calcular_margenes(meses_idx[-1])
    sin_match = asignar_margenes(p["top10"], m_ovq, m_aml)

    print(f"Margenes leidos: {len(m_ovq)} productos OVQ, {len(m_aml)} productos AML (AML de {mes_aml})\n")
    print("Top 10 con margen de referencia:")
    for i, prod in enumerate(p["top10"], 1):
        linea = f"  {i:2}. [{prod['marca']}] {prod['producto']:<42} {numero(prod['kg_total'], 1):>8} kg"
        if prod["marca"] == "OVQ":
            print(f"{linea}   {prod['margen_txt']}")
        else:
            print(linea)
            if prod["canales"]:
                print("        " + "  ".join(f"{c}: {pesos(v)}/kg" for c, v in prod["canales"].items()))
            else:
                print("        (sin margen en AML MARGEN)")

    if sin_match:
        print("\nProductos sin margen encontrado (puede ser que el nombre difiera entre planillas):")
        for s in sin_match:
            print("  -", s)
