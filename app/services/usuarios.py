from datetime import datetime

from flask_babel import gettext as _
from sqlalchemy import select, func, or_

from app.extensions import db
from app.models.enum import RolUsuario, NivelUsuario, Categoria, AccionAuditoria, EstadoTicket
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    ErrorPersistencia,
    OperacionNoPermitidaError,
    UsuarioNoEncontradoError,
)

FILTROS_ESTADO = ("activos", "inactivos", "bloqueados")


class ServicioUsuarios:

    @staticmethod
    def _guardar(mensaje):
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"{mensaje}, error: {e}")
            raise ErrorPersistencia(mensaje) from e

    @staticmethod
    def obtener(usuario_id):
        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None:
            raise UsuarioNoEncontradoError(_("El usuario no existe"))
        return usuario

    @staticmethod
    def listar(busqueda=None, rol=None, estado=None, area=None, pagina=1, por_pagina=25):
        query = select(Usuario)
        if busqueda:
            patron = f"%{busqueda.strip()}%"
            query = query.where(or_(Usuario.nombre.ilike(patron), Usuario.email.ilike(patron)))
        if rol is not None:
            query = query.where(Usuario.rol == rol)
        if area is not None:
            query = query.where(Usuario.area_soporte == area)
        if estado == "activos":
            query = query.where(Usuario.activo.is_(True))
        elif estado == "inactivos":
            query = query.where(Usuario.activo.is_(False))
        elif estado == "bloqueados":
            query = query.where(Usuario.bloqueado_hasta.isnot(None), Usuario.bloqueado_hasta > datetime.now())
        query = query.order_by(Usuario.activo.desc(), Usuario.nombre)
        return db.paginate(query, page=pagina, per_page=por_pagina, error_out=False)

    @staticmethod
    def resumen():
        ahora = datetime.now()
        total = db.session.execute(select(func.count(Usuario.id))).scalar()
        inactivos = db.session.execute(select(func.count(Usuario.id)).where(Usuario.activo.is_(False))).scalar()
        bloqueados = db.session.execute(
            select(func.count(Usuario.id)).where(Usuario.bloqueado_hasta.isnot(None), Usuario.bloqueado_hasta > ahora)
        ).scalar()
        por_rol = dict(db.session.execute(select(Usuario.rol, func.count(Usuario.id)).group_by(Usuario.rol)).all())
        return {
            "total": total,
            "inactivos": inactivos,
            "bloqueados": bloqueados,
            "admins": por_rol.get(RolUsuario.ADMIN, 0),
            "agentes": por_rol.get(RolUsuario.AGENTE, 0),
            "finales": por_rol.get(RolUsuario.FINAL, 0),
        }

    @staticmethod
    def _admins_activos(excluir_id=None):
        query = select(func.count(Usuario.id)).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True))
        if excluir_id is not None:
            query = query.where(Usuario.id != excluir_id)
        return db.session.execute(query).scalar()

    @staticmethod
    def carga_actual(usuario_id):
        return db.session.execute(
            select(func.count(Ticket.id)).where(Ticket.agente_id == usuario_id, Ticket.estado == EstadoTicket.EN_PROGRESO)
        ).scalar()

    @staticmethod
    def actualizar(admin_id, usuario_id, nombre, rol, nivel, area_soporte=None):
        usuario = ServicioUsuarios.obtener(usuario_id)
        nombre = (nombre or "").strip()
        if len(nombre) < 2:
            raise ValueError(_("El nombre debe tener al menos 2 caracteres"))
        if len(nombre) > 100:
            raise ValueError(_("El nombre no puede superar los 100 caracteres"))
        if not isinstance(rol, RolUsuario) or not isinstance(nivel, NivelUsuario):
            raise ValueError(_("Rol o nivel no válido"))
        if area_soporte is not None and not isinstance(area_soporte, Categoria):
            raise ValueError(_("Área no válida"))
        if rol == RolUsuario.AGENTE and area_soporte is None:
            raise ValueError(_("Un agente debe tener un área de soporte"))
        if rol != RolUsuario.AGENTE:
            area_soporte = None

        if usuario.rol == RolUsuario.ADMIN and rol != RolUsuario.ADMIN:
            if usuario.id == admin_id:
                raise OperacionNoPermitidaError(_("No puedes quitarte tu propio rol de administrador"))
            if ServicioUsuarios._admins_activos(excluir_id=usuario.id) == 0:
                raise OperacionNoPermitidaError(_("Debe quedar al menos un administrador activo"))

        if usuario.rol == RolUsuario.AGENTE and (rol != RolUsuario.AGENTE or area_soporte != usuario.area_soporte):
            if ServicioUsuarios.carga_actual(usuario.id) > 0:
                raise OperacionNoPermitidaError(
                    _("El agente tiene tickets en progreso. Reasígnalos antes de cambiar su rol o área.")
                )

        cambios = []
        if usuario.nombre != nombre:
            cambios.append(_("nombre"))
        if usuario.rol != rol:
            cambios.append(_("rol: %(a)s → %(b)s", a=usuario.rol.value, b=rol.value))
        if usuario.nivel != nivel:
            cambios.append(_("nivel: %(a)s → %(b)s", a=usuario.nivel.value, b=nivel.value))
        if usuario.area_soporte != area_soporte:
            cambios.append(_("área: %(a)s → %(b)s",
                             a=usuario.area_soporte.value if usuario.area_soporte else "—",
                             b=area_soporte.value if area_soporte else "—"))
        if not cambios:
            return usuario, False

        usuario.nombre = nombre
        usuario.rol = rol
        usuario.nivel = nivel
        usuario.area_soporte = area_soporte
        ServicioUsuarios._guardar(_("No se pudo actualizar el usuario"))
        ServicioAuditoria.registrar(
            usuario_id=admin_id,
            accion=AccionAuditoria.EDITAR_USUARIO,
            detalle=_("Usuario %(p1)s editado (%(p2)s)", p1=usuario.email, p2=", ".join(cambios)),
        )
        return usuario, True

    @staticmethod
    def cambiar_activo(admin_id, usuario_id, activo):
        usuario = ServicioUsuarios.obtener(usuario_id)
        if usuario.activo == activo:
            return usuario
        if not activo:
            if usuario.id == admin_id:
                raise OperacionNoPermitidaError(_("No puedes desactivar tu propia cuenta"))
            if usuario.rol == RolUsuario.ADMIN and ServicioUsuarios._admins_activos(excluir_id=usuario.id) == 0:
                raise OperacionNoPermitidaError(_("Debe quedar al menos un administrador activo"))
            if ServicioUsuarios.carga_actual(usuario.id) > 0:
                raise OperacionNoPermitidaError(
                    _("El usuario tiene tickets en progreso asignados. Reasígnalos antes de desactivarlo.")
                )
        usuario.activo = activo
        ServicioUsuarios._guardar(_("No se pudo cambiar el estado del usuario"))
        ServicioAuditoria.registrar(
            usuario_id=admin_id,
            accion=AccionAuditoria.REACTIVAR_USUARIO if activo else AccionAuditoria.DESACTIVAR_USUARIO,
            detalle=(_("Cuenta reactivada: %(p1)s", p1=usuario.email) if activo
                     else _("Cuenta desactivada: %(p1)s", p1=usuario.email)),
        )
        return usuario

    @staticmethod
    def desbloquear(admin_id, usuario_id):
        usuario = ServicioUsuarios.obtener(usuario_id)
        usuario.bloqueado_hasta = None
        usuario.intentos_fallidos = 0
        ServicioUsuarios._guardar(_("No se pudo desbloquear al usuario"))
        ServicioAuditoria.registrar(
            usuario_id=admin_id,
            accion=AccionAuditoria.DESBLOQUEO_USUARIO,
            detalle=_("Desbloqueo manual de %(p1)s por un administrador", p1=usuario.email),
        )
        return usuario

    @staticmethod
    def restablecer_doble_factor(admin_id, usuario_id):
        from app.services.doble_factor import ServicioDobleFactor

        usuario = ServicioUsuarios.obtener(usuario_id)
        registro = ServicioDobleFactor.obtener_registro(usuario.id)
        if registro is None:
            raise OperacionNoPermitidaError(_("El usuario no tiene configurada la verificación en dos pasos"))
        db.session.delete(registro)
        ServicioUsuarios._guardar(_("No se pudo restablecer la verificación en dos pasos"))
        ServicioAuditoria.registrar(
            usuario_id=admin_id,
            accion=AccionAuditoria.RESTABLECER_2FA_ADMIN,
            detalle=_("Verificación en dos pasos restablecida para %(p1)s", p1=usuario.email),
        )
        return usuario

    @staticmethod
    def enviar_recuperacion(admin_id, usuario_id):
        from app.services.recuperacion import ServicioRecuperacion

        usuario = ServicioUsuarios.obtener(usuario_id)
        if not usuario.activo:
            raise OperacionNoPermitidaError(_("La cuenta está desactivada"))
        token = ServicioRecuperacion.solicitar(usuario.email)
        if token is None:
            raise OperacionNoPermitidaError(
                _("Se alcanzó el límite de enlaces de recuperación para este usuario. Intenta más tarde.")
            )
        return usuario

    @staticmethod
    def registrar_acceso(usuario):
        usuario.ultimo_acceso = datetime.now()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo registrar el último acceso, error: {e}")
