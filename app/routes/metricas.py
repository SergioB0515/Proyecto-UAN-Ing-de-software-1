from flask import Blueprint, render_template, Response, request
from flask_babel import gettext as _
from app.traducciones import etiqueta
from app.services.metricas import ServicioMetricas
from app.routes.decoradores import requiere_admin
import csv
import io
from openpyxl import Workbook
metricas_bp = Blueprint("metricas", __name__)


@metricas_bp.route("/metricas")
@requiere_admin  
def mostrar_metricas():  
    metricas = ServicioMetricas.obtener_metricas()  

    return render_template("panel_metricas.html",metricas=metricas)  

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