import uuid
from datetime import datetime, timedelta

from app.extensions import db
from app.models.enum import Categoria, EstadoTicket, NivelUsuario, Prioridad, RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.autenticacion import ServicioAutenticacion

CONTRASENA = "ClaveSegura123!"


def crear_usuario(rol=RolUsuario.FINAL, area=None, nivel=NivelUsuario.NORMAL, nombre=None, activo=True):
    sufijo = uuid.uuid4().hex[:10]
    usuario = Usuario(
        nombre=nombre or f"Usuario {rol.value} {sufijo}",
        email=f"prueba_{rol.value}_{sufijo}@empresa.com",
        contrasena_hash=ServicioAutenticacion._generar_hash(CONTRASENA),
        rol=rol,
        area_soporte=area,
        nivel=nivel,
        activo=activo,
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


def crear_ticket(creador, categoria=Categoria.REDES, prioridad=Prioridad.MEDIA, estado=EstadoTicket.ABIERTO,
                 agente=None, creado_hace_horas=1, horas_sla=24, horas_hasta_cierre=None, texto="la red no funciona en el piso"):
    ahora = datetime.now()
    creado = ahora - timedelta(hours=creado_hace_horas)
    ticket = Ticket(
        texto=texto,
        categoria=categoria,
        prioridad=prioridad,
        estado=estado,
        creador_id=creador.id,
        agente_id=agente.id if agente else None,
        fecha_creacion=creado,
        fecha_asignacion=creado if agente else None,
        fecha_limite=creado + timedelta(hours=horas_sla),
        fecha_cierre=(creado + timedelta(hours=horas_hasta_cierre)) if horas_hasta_cierre is not None else None,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket
