from flask import Blueprint, render_template
from app.services.metricas import ServicioMetricas
from app.routes.decoradores import requiere_admin

metricas_bp = Blueprint("metricas", __name__)


@metricas_bp.route("/metricas")
@requiere_admin  
def mostrar_metricas():  
    metricas = ServicioMetricas.obtener_metricas()  

    return render_template("panel_metricas.html",metricas=metricas)  