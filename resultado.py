"""Bloque 01 - Resultado: ventas, resultado neto, kilos, capacidad y punto de equilibrio."""
from google_sheets import conectar, leer_hoja

ADMIN_ID = "1V7r0Vs_6FNtKQdbRBtKlsIQ-fmEyU3e3h-QD2t69cgo"
CAPACIDAD_KG_MES = 6500
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def limpiar(texto):
    """'Descuentos  OVQ ' -> 'DESCUENTOS OVQ' (mayusculas y espacios simples)."""
    return " ".join(str(texto).split()).upper()


def indexar_filas(filas):
    """Arma un diccionario: etiqueta de la columna A -> lista de filas con esa etiqueta."""
    indice = {}
    for fila in filas:
        if fila and str(fila[0]).strip():
            indice.setdefault(limpiar(fila[0]), []).append(fila)
    return indice


def serie(indice, etiqueta, aparicion=1):
    """Los 12 valores mensuales (columnas B a M) de una fila. Celdas vacias o texto -> 0."""
    clave = limpiar(etiqueta)
    if clave not in indice or len(indice[clave]) < aparicion:
        raise KeyError(f"No encontre la fila '{etiqueta}' (aparicion {aparicion}) en RESULTADOS")
    fila = indice[clave][aparicion - 1]
    valores = [v if isinstance(v, (int, float)) else 0 for v in fila[1:13]]
    return valores + [0] * (12 - len(valores))   # filas cortas: completar con ceros


def pesos(v):
    return "$" + f"{v:,.0f}".replace(",", ".")


def numero(v, decimales=0):
    texto = f"{v:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def calcular():
    sheets = conectar()
    filas = leer_hoja(sheets, ADMIN_ID, "RESULTADOS")
    idx = indexar_filas(filas)

    ingresos = serie(idx, "INGRESOS")
    # Meses "cargados" = los que tienen ingresos > 0
    meses = [i for i, v in enumerate(ingresos) if v > 0]
    if not meses:
        raise ValueError("RESULTADOS no tiene ningun mes con ingresos cargados")
    ult = meses[-1]

    def del_anio(s):          # se queda solo con los meses cargados
        return [s[i] for i in meses]

    ventas_ovq = serie(idx, "OVUNQUE", aparicion=1)
    ventas_aml = serie(idx, "AMOLA", aparicion=1)
    kilos_ovq = serie(idx, "KILOS VENDIDOS OVUNQUE")
    kilos_aml = serie(idx, "KILOS VENDIDOS AMOLA")
    resultado = serie(idx, "RESULTADO ECONÓMICO")
    egresos = serie(idx, "EGRESOS")
    impuestos = [a + b + c for a, b, c in zip(serie(idx, "IVA"),
                                               serie(idx, "IIBB (4%)"),
                                               serie(idx, "ARBA (1%) y Transf (0,006)"))]
    kilos = [a + b for a, b in zip(kilos_ovq, kilos_aml)]

    ventas_tot = sum(del_anio(ingresos))
    resultado_tot = sum(del_anio(resultado))
    kilos_tot = sum(del_anio(kilos))

    # Punto de equilibrio recalculado:
    # margen de contribucion por kg = (ingresos - egresos - impuestos) / kilos
    # kilos de equilibrio = costos fijos promedio por mes / margen de contribucion por kg
    contrib_kg = (ventas_tot - sum(del_anio(egresos)) - sum(del_anio(impuestos))) / kilos_tot
    fijos = [v for v in serie(idx, "FIJOS ESTIMADOS") if v > 0]
    fijos_prom = sum(fijos) / len(fijos) if fijos else None
    kg_equilibrio = fijos_prom / contrib_kg if fijos_prom and contrib_kg > 0 else None

    return {
        "meses": [MESES[i] for i in meses],
        "ventas": ventas_tot,
        "ventas_ult": ingresos[ult],
        "resultado": resultado_tot,
        "resultado_pct": resultado_tot / ventas_tot * 100,
        "resultado_ult": resultado[ult],
        "kilos": kilos_tot,
        "kilos_ult": kilos[ult],
        "cap_prom_pct": kilos_tot / len(meses) / CAPACIDAD_KG_MES * 100,
        "cap_ult_pct": kilos[ult] / CAPACIDAD_KG_MES * 100,
        "ovq_tot": sum(del_anio(ventas_ovq)),
        "aml_tot": sum(del_anio(ventas_aml)),
        "contrib_kg": contrib_kg,
        "fijos_prom": fijos_prom,
        "fijos_meses": len(fijos),
        "kg_equilibrio": kg_equilibrio,
        # series mes a mes, para el grafico de barras
        "serie_ovq": del_anio(ventas_ovq),
        "serie_aml": del_anio(ventas_aml),
        "serie_kilos": del_anio(kilos),
    }


if __name__ == "__main__":
    r = calcular()
    ult = r["meses"][-1]
    print(f"Meses cargados: {r['meses'][0]}-{ult}\n")
    print(f"Ventas acumuladas:   {pesos(r['ventas'])}   (ultimo mes: {pesos(r['ventas_ult'])})")
    print(f"Resultado neto:      {pesos(r['resultado'])}   ({numero(r['resultado_pct'], 1)}%)")
    print(f"Kilos vendidos:      {numero(r['kilos'])} kg   (ultimo mes: {numero(r['kilos_ult'], 1)} kg)")
    print(f"Capacidad usada:     {numero(r['cap_prom_pct'], 1)}% promedio   ({ult}: {numero(r['cap_ult_pct'], 1)}%)")
    share = r["ovq_tot"] / (r["ovq_tot"] + r["aml_tot"]) * 100
    print(f"Split por marca:     OVQ {share:.0f}% ({pesos(r['ovq_tot'])})  -  AML {100 - share:.0f}% ({pesos(r['aml_tot'])})")
    print()
    print(f"Margen contribucion: {pesos(r['contrib_kg'])}/kg")
    if r["kg_equilibrio"]:
        print(f"Fijos promedio:      {pesos(r['fijos_prom'])}/mes ({r['fijos_meses']} meses cargados)")
        print(f"Kilos de equilibrio: {numero(r['kg_equilibrio'])} kg "
              f"({numero(r['kg_equilibrio'] / CAPACIDAD_KG_MES * 100, 1)}% de la capacidad)")
    else:
        print("Kilos de equilibrio: falta cargar FIJOS ESTIMADOS en RESULTADOS")
