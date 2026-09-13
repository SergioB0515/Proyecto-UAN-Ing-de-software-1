from flask import Blueprint, render_template, Response, request
from flask_babel import gettext as _
from app.traducciones import etiqueta
from app.services.metricas import ServicioMetricas
from app.models.enum import Categoria
from app.routes.decoradores import requiere_admin
import csv
import io
from openpyxl import Workbook
metricas_bp = Blueprint("metricas", __name__)


@metricas_bp.route("/metricas")
@requiere_admin
def mostrar_metricas():
    metricas = ServicioMetricas.obtener_metricas()

    metricas_confianza = ServicioMetricas.obtener_metricas_confianza_clasificador()

    metricas_por_area = {
        area : ServicioMetricas.metricas_por_agente(area=area)
        for area in Categoria
    }

    resumen_por_area = {}
    grafico_por_area = {}
    etiquetas_todas, valores_todas = [], []
    for area, agentes in metricas_por_area.items():
        cerrados = sum(a["tickets_cerrados"] for a in agentes)
        slas = [a["cumplimiento_sla"] for a in agentes if a["cumplimiento_sla"] is not None]
        resumen_por_area[area] = {
            "cantidad_agentes": len(agentes),
            "tickets_cerrados": cerrados,
            "cumplimiento_sla_promedio": (sum(slas) / len(slas)) if slas else None,
        }

        etiquetas, valores = [], []
        for a in agentes:
            if a["cumplimiento_sla"] is not None:
                etiquetas.append(a["nombre"])
                valores.append(round(a["cumplimiento_sla"] * 100, 1))
                etiquetas_todas.append(f"{a['nombre']} ({etiqueta(area.value)})")
                valores_todas.append(round(a["cumplimiento_sla"] * 100, 1))
        grafico_por_area[area.value] = {"etiquetas": etiquetas, "valores": valores}

    grafico_por_area["todas"] = {"etiquetas": etiquetas_todas, "valores": valores_todas}

    return render_template(
        "panel_metricas.html",
        metricas=metricas,
        metricas_confianza=metricas_confianza,
        metricas_por_area=metricas_por_area,
        resumen_por_area=resumen_por_area,
        grafico_por_area=grafico_por_area,
    )

@metricas_bp.route("/metricas/exportar")
@requiere_admin
def exportar_metricas():
    metricas = ServicioMetricas.obtener_metricas()
    formato = request.args.get("formato", "csv")

    filas = []

    for estado, cantidad in metricas["tickets_por_estado"].items():
        filas.append((_("Tickets por estado - %(valor)s", valor=etiqueta(estado)), cantidad))

    for categoria, cantidad in metricas["tickets_por_categoria"].items():
        filas.append((_("Tickets por categoría - %(valor)s", valor=etiqueta(categoria)), cantidad))

    for prioridad, cantidad in metricas["tickets_por_prioridad"].items():
        filas.append((_("Tickets por prioridad - %(valor)s", valor=etiqueta(prioridad)), cantidad))

    filas.append((_("Tickets vencidos actualmente"), metricas["tickets_vencidos_actualmente"]))
    filas.append((_("Tickets próximos a vencer"), metricas["tickets_proximos_a_vencer_actualmente"]))
    filas.append((_("Tickets vencidos últimos 30 días"), metricas["tickets_vencidos_ultimos_30_dias"]))
    filas.append((_("Cantidad de agentes"), metricas["cantidad_agentes"]))

    if formato == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.append([_("Métrica"), _("Valor")])
        for nombre, valor in filas:
            ws.append([nombre, valor])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return Response(
            buffer.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=metricas.xlsx"}
        )
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([_("Métrica"), _("Valor")])
        for nombre, valor in filas:
            writer.writerow([nombre, valor])

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=metricas.csv"}
        )
        
