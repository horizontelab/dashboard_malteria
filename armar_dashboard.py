"""Junta todos los bloques y genera dist/index.html a partir de plantilla.html."""
import json
import os
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from resultado import CAPACIDAD_KG_MES, MESES, calcular
from productos import calcular_productos
from margenes import asignar_margenes, calcular_margenes
from cobranzas import calcular_cobranzas
from fabricas import calcular_fabricas, rangos
from varios import calcular_varios

TZ = ZoneInfo("America/Argentina/Buenos_Aires")


def armar(salida="dist"):
    estado = []

    def bloque(nombre, fn):
        """Corre un bloque; si falla, lo anota y sigue con los demas."""
        try:
            valor = fn()
            estado.append({"bloque": nombre, "ok": True})
            return valor
        except Exception as e:
            traceback.print_exc()
            estado.append({"bloque": nombre, "ok": False, "error": str(e)[:200]})
            return None

    ahora = datetime.now(TZ)
    datos = {"generado": ahora.strftime("%d/%m/%Y %H:%M"), "anio": ahora.year,
             "capacidad": CAPACIDAD_KG_MES}

    r = bloque("Resultado (hoja RESULTADOS)", calcular)
    datos["resultado"] = r
    if r:
        meses_idx = [MESES.index(m) for m in r["meses"]]
        p = bloque("Productos (VOLUMEN y VENTAS)", lambda: calcular_productos(meses_idx))
        if p:
            mg = bloque("Margenes (COSTOS y Precios)", lambda: calcular_margenes(meses_idx[-1]))
            if mg:
                m_ovq, m_aml, mes_aml = mg
                asignar_margenes(p["top10"], m_ovq, m_aml)
                datos["mes_margen_aml"] = mes_aml
            datos["productos"] = {"top10": p["top10"], "por_mes": p["por_mes"], "detalle": p["detalle"]}

        cb = bloque("Cobranzas y concentracion (Administracion)", lambda: calcular_cobranzas(meses_idx))
        if cb:
            cxc, hist, conc = cb
            datos["cobranzas"] = {"total": cxc["total"], "ordenes": cxc["ordenes"],
                                  "por_estado": cxc["por_estado"], "deudores": cxc["deudores"][:6],
                                  "pendientes": cxc["pendientes"][:8], "ambiguas": len(cxc["ambiguas"])}
            datos["historico"] = {k: hist[k] for k in ("total", "facturas", "ultima_factura")}
            datos["concentracion"] = {"total": conc["total"], "clientes": conc["clientes"],
                                      "pct_top": conc["pct_top"], "top_n": conc["top_n"],
                                      "ranking": conc["ranking"][:5]}

    fb = bloque("Reposicion fabricas (5 planillas de pedidos)", calcular_fabricas)
    if fb:
        res, hasta, hoy = fb
        lista = []
        for nombre, f in res.items():
            if "error" in f:
                lista.append({"n": nombre, "error": f["error"]})
                continue
            falta = []
            if f["sin_planilla"]:
                falta.append(f"{rangos(f['sin_planilla'])} (sin planilla)")
            if f["vacias"]:
                falta.append(f"{rangos(f['vacias'])} (planilla vacia)")
            lista.append({"n": nombre, "activos": f["activos"], "total": f["total"],
                          "falta": " · ".join(falta), "kilos": f["kilos_anio"],
                          "mes_en_curso": f["mes_en_curso"]})
        datos["fabricas"] = {"hasta": MESES[hasta - 1], "meses": hasta, "mes_en_curso": MESES[hoy.month - 1],
                             "lista": sorted(lista, key=lambda x: -x.get("activos", -1))}

    v = bloque("Stock, mijo y sueldos", calcular_varios)
    if v:
        nombres = {"stock": "Stock Amola", "mijo": "Compra granos (Castro)", "sueldos": "Sueldos socias (TAREAS)"}
        for k, nombre in nombres.items():
            if "error" in v[k]:
                estado.append({"bloque": nombre, "ok": False, "error": v[k]["error"]})
            else:
                datos[k] = v[k]
        if "sueldos" in datos and datos["sueldos"]["meses"]:
            m = datos["sueldos"]["meses"]
            datos["sueldos"]["meses_txt"] = f"{MESES[m[0]]}–{MESES[m[-1]]}"

    datos["estado"] = estado
    plantilla = open("plantilla.html", encoding="utf-8").read()
    js = json.dumps(datos, ensure_ascii=False, default=str).replace("</", "<\\/")
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "index.html"), "w", encoding="utf-8") as f:
        f.write(plantilla.replace("__DATOS__", js))
    return datos


if __name__ == "__main__":
    d = armar()
    ok = sum(e["ok"] for e in d["estado"])
    print(f"\nDashboard generado en dist/index.html ({ok} de {len(d['estado'])} bloques OK)")
    for e in d["estado"]:
        if not e["ok"]:
            print(f"  ERROR en {e['bloque']}: {e['error']}")
