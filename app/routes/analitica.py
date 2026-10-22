import csv
import io

from flask import Blueprint, Response, render_template, request
from flask_babel import gettext as _

from app.models.enum import Categoria
from app.routes.decoradores import requiere_admin
from app.services.analitica import ServicioAnalitica, PERIODOS_VALIDOS
from app.traducciones import etiqueta

analitica_bp = Blueprint("analitica", __name__)


def _filtros():
    dias = ServicioAnalitica.normalizar_periodo(request.args.get("dias", 30))
    categoria = None
    if request.args.get("categoria"):
        try:
            categoria = Categoria(request.args["categoria"])
        except ValueError:
            categoria = None
    return dias, categoria


@analitica_bp.route("/analitica")
@requiere_admin
def panel():
    dias, categoria = _filtros()
    return render_template(
        "analitica.html",
        datos=ServicioAnalitica.panel(dias=dias, categoria=categoria),
        periodos=PERIODOS_VALIDOS,
    )


@analitica_bp.route("/analitica/exportar")
@requiere_admin
def exportar():
    dias, categoria = _filtros()
    datos = ServicioAnalitica.panel(dias=dias, categoria=categoria)
    buffer = io.StringIO()
    escritor = csv.writer(buffer)

    escritor.writerow([_("Indicador"), _("Valor"), _("Periodo anterior")])
    nombres = {
        "creados": _("Tickets creados"), "cerrados": _("Tickets cerrados"),
        "mttr_horas": _("Tiempo medio de resolución (h)"), "mediana_horas": _("Mediana de resolución (h)"),
        "sla_pct": _("Cumplimiento de SLA (%)"), "primera_respuesta_horas": _("Primera respuesta, mediana (h)"),
        "con_respuesta_pct": _("Tickets con respuesta (%)"),
    }
    for clave, nombre in nombres.items():
        escritor.writerow([nombre, datos["kpis"][clave], datos["anterior"][clave]])
    escritor.writerow([_("CSAT (%)"), datos["csat"]["csat"], datos["csat_anterior"]["csat"]])
    escritor.writerow([])

    escritor.writerow([_("Categoría"), _("Creados"), _("Cerrados"), _("Abiertos"), _("MTTR (h)"), _("SLA (%)")])
    for fila in datos["por_categoria"]:
        escritor.writerow([etiqueta(fila["categoria"]), fila["creados"], fila["cerrados"], fila["abiertos"],
                           fila["mttr_horas"], fila["sla_pct"]])
    escritor.writerow([])

    escritor.writerow([_("Agente"), _("Área"), _("Cerrados"), _("Carga actual"), _("MTTR (h)"), _("SLA (%)"), _("CSAT")])
    for fila in datos["agentes"]:
        escritor.writerow([fila["nombre"], etiqueta(fila["area"]), fila["cerrados"], fila["carga"],
                           fila["mttr_horas"], fila["sla_pct"], fila["csat"]])

    return Response(
        "﻿" + buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=analitica_{dias}d.csv"},
    )
