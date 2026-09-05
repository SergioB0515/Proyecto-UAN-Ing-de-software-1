
from flask import Blueprint, render_template, request, Response
from app.services.auditoria import ServicioAuditoria
from app.models.log_auditoria import LogAuditoria
from app.routes.decoradores import requiere_admin
from app.models.enum import AccionAuditoria
from app.models.usuario import Usuario
from app.extensions import db
from sqlalchemy import select
import csv
import io
from openpyxl import Workbook
from datetime import datetime,timedelta
auditoria_bp = Blueprint("auditoria", __name__)


@auditoria_bp.route("/auditoria")
@requiere_admin
def mostrar_auditoria():
    usuario_id = request.args.get("usuario_id", type=int) 

    accion_raw = request.args.get("accion")
    accion = None
    if accion_raw:
        try:
            accion = AccionAuditoria(accion_raw)
        except ValueError:
            accion = None

    fecha_desde_raw = request.args.get("fecha_desde")  
    fecha_desde = None
    if fecha_desde_raw:  
        try:
            fecha_desde = datetime.strptime(fecha_desde_raw, "%Y-%m-%d")
        except ValueError:
            fecha_desde = None

    fecha_hasta_raw = request.args.get("fecha_hasta") 
    fecha_hasta = None
    if fecha_hasta_raw:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_raw, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            fecha_hasta = None

    pagina = request.args.get("pagina", 1, type=int)
    

    
    logs_paginados = ServicioAuditoria.listar_logs(
        usuario_id=usuario_id,
        accion=accion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        
    )


    ids_en_pagina = {i.usuario_id for i in logs_paginados.items}
    usuarios_en_pagina = db.session.execute(select(Usuario).where(Usuario.id.in_(ids_en_pagina))).scalars().all()
    nombres_por_id = {u.id : u.nombre  for u in usuarios_en_pagina}


    todos_los_usuarios = db.session.execute(select(Usuario)).scalars().all()
    filtros_actuales = {
    "usuario_id": usuario_id,
    "accion": accion_raw,
    "fecha_desde": fecha_desde_raw,
    "fecha_hasta": fecha_hasta_raw,
}
    return render_template(
        "auditoria.html",
        logs=logs_paginados,
        nombres_por_id=nombres_por_id,
        usuarios=todos_los_usuarios,
        filtros_actuales=filtros_actuales
    )
    
@auditoria_bp.route("/auditoria/exportar")
@requiere_admin
def exportar_auditoria():
    usuario_id = request.args.get("usuario_id", type=int) 

    accion_raw = request.args.get("accion")
    accion = None
    if accion_raw:
        try:
            accion = AccionAuditoria(accion_raw)
        except ValueError:
            accion = None

    fecha_desde_raw = request.args.get("fecha_desde")  
    fecha_desde = None
    if fecha_desde_raw:  
        try:
            fecha_desde = datetime.strptime(fecha_desde_raw, "%Y-%m-%d")
        except ValueError:
            fecha_desde = None

    fecha_hasta_raw = request.args.get("fecha_hasta") 
    fecha_hasta = None
    if fecha_hasta_raw:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_raw, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            fecha_hasta = None

    logs = ServicioAuditoria.listar_logs(
        usuario_id=usuario_id, accion=accion, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        sin_paginar=True
    )

    ids_en_logs = {i.usuario_id for i in logs}
    usuarios_en_logs = db.session.execute(select(Usuario).where(Usuario.id.in_(ids_en_logs))).scalars().all()
    nombres_por_id = {u.id : u.nombre  for u in usuarios_en_logs}

    formato = request.args.get("formato", "csv")
    encabezados = ["Fecha", "Usuario", "Acción", "Detalle"]

    if formato == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.append(encabezados)
        for log in logs:

            ws.append([
                log.fecha,
                nombres_por_id.get(log.usuario_id, "Desconocido"),
                log.accion.value,
                log.detalle
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return Response(
            buffer.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=auditoria.xlsx"}
        )
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(encabezados)
        for log in logs:

            writer.writerow([
                log.fecha,
                nombres_por_id.get(log.usuario_id, "Desconocido"),
                log.accion.value,
                log.detalle
            ])

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=auditoria.csv"}
        )