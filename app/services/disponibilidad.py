from datetime import datetime

from flask_babel import gettext as _
from sqlalchemy import and_, func, or_, select

from app.extensions import db
from app.models.enum import AccionAuditoria, Categoria, RolUsuario
from app.models.usuario import Usuario
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    AusenciaInvalidaError,
    ErrorPersistencia,
    OperacionNoPermitidaError,
    UsuarioNoEncontradoError,
)

MAX_MOTIVO = 120


class ServicioDisponibilidad:
    """Disponibilidad declarada de un agente.

    La ausencia se guarda como una ventana de fechas en el propio usuario
    (ausente_desde / ausente_hasta). No hay un campo booleano aparte: la
    disponibilidad se deriva siempre de la ventana, para que no existan dos
    fuentes de verdad que puedan quedar desincronizadas.

    Un agente esta AUSENTE cuando:
        ausente_desde no es nulo
        y ausente_desde <= ahora
        y (ausente_hasta es nulo o ahora < ausente_hasta)

    ausente_hasta nulo significa "ausente hasta nuevo aviso".
    """

    # ---------------------------------------------------------------- lectura

    @staticmethod
    def filtro_disponible(ahora=None):
        """Condicion SQL que deja pasar solo a los usuarios disponibles.

        Es la negacion exacta de la regla de ausencia documentada arriba, para
        poder filtrar en la consulta en vez de traer todo y filtrar en Python.
        """
        ahora = ahora or datetime.now()
        return or_(
            Usuario.ausente_desde.is_(None),
            Usuario.ausente_desde > ahora,
            and_(Usuario.ausente_hasta.isnot(None), Usuario.ausente_hasta <= ahora),
        )

    @staticmethod
    def esta_disponible(usuario, ahora=None):
        if usuario is None:
            return False
        if usuario.ausente_desde is None:
            return True
        ahora = ahora or datetime.now()
        if usuario.ausente_desde > ahora:
            return True
        if usuario.ausente_hasta is not None and usuario.ausente_hasta <= ahora:
            return True
        return False

    @staticmethod
    def esta_ausente(usuario, ahora=None):
        return usuario is not None and not ServicioDisponibilidad.esta_disponible(usuario, ahora)

    @staticmethod
    def agentes_disponibles(categoria, ahora=None):
        """Agentes activos y disponibles del area indicada."""
        return db.session.execute(
            select(Usuario).where(
                Usuario.rol == RolUsuario.AGENTE,
                Usuario.area_soporte == categoria,
                Usuario.activo.is_(True),
                ServicioDisponibilidad.filtro_disponible(ahora),
            ).order_by(Usuario.nombre)
        ).scalars().all()

    @staticmethod
    def admins_activos():
        return db.session.execute(
            select(Usuario).where(Usuario.rol == RolUsuario.ADMIN, Usuario.activo.is_(True))
        ).scalars().all()

    @staticmethod
    def cobertura_area(categoria, ahora=None):
        """Conteo de agentes activos / disponibles / ausentes de un area."""
        ahora = ahora or datetime.now()
        base = (
            select(func.count(Usuario.id))
            .where(
                Usuario.rol == RolUsuario.AGENTE,
                Usuario.area_soporte == categoria,
                Usuario.activo.is_(True),
            )
        )
        activos = db.session.execute(base).scalar() or 0
        disponibles = db.session.execute(
            base.where(ServicioDisponibilidad.filtro_disponible(ahora))
        ).scalar() or 0
        return {
            "area": categoria,
            "activos": activos,
            "disponibles": disponibles,
            "ausentes": activos - disponibles,
            "sin_cobertura": disponibles == 0,
        }

    @staticmethod
    def cobertura_todas_las_areas(ahora=None):
        ahora = ahora or datetime.now()
        return [ServicioDisponibilidad.cobertura_area(area, ahora) for area in Categoria]

    @staticmethod
    def areas_sin_cobertura(ahora=None):
        ahora = ahora or datetime.now()
        return [c["area"] for c in ServicioDisponibilidad.cobertura_todas_las_areas(ahora) if c["sin_cobertura"]]

    @staticmethod
    def ausentes(ahora=None):
        """Agentes activos que hoy estan dentro de su ventana de ausencia."""
        ahora = ahora or datetime.now()
        return db.session.execute(
            select(Usuario).where(
                Usuario.rol == RolUsuario.AGENTE,
                Usuario.activo.is_(True),
                ~ServicioDisponibilidad.filtro_disponible(ahora),
            ).order_by(Usuario.area_soporte, Usuario.nombre)
        ).scalars().all()

    # --------------------------------------------------------------- escritura

    @staticmethod
    def _guardar(mensaje, objeto=None):
        """Confirma los cambios y, si falla, deja el objeto como estaba.

        El refresh tras el rollback evita el objeto fantasma: sin el, el usuario
        en memoria se queda con la ventana de ausencia que no llego a guardarse.
        """
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            if objeto is not None:
                try:
                    db.session.refresh(objeto)
                except Exception:
                    pass
            print(f"{mensaje}, error: {e}")
            raise ErrorPersistencia(mensaje) from e

    @staticmethod
    def _obtener(usuario_id):
        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None:
            raise UsuarioNoEncontradoError(_("El usuario no existe"))
        return usuario

    @staticmethod
    def _tickets_vivos_del_agente(usuario_id):
        from app.models.ticket import Ticket
        from app.services.tickets import ESTADOS_ABIERTOS

        return db.session.execute(
            select(Ticket).where(
                Ticket.agente_id == usuario_id,
                Ticket.estado.in_(ESTADOS_ABIERTOS),
            )
        ).scalars().all()

    @staticmethod
    def marcar_tickets_para_cobertura(usuario):
        """Marca los tickets vivos de un agente ausente y avisa a su area.

        En la 3.1 la ausencia solo sacaba al agente de las sugerencias: los
        tickets que ya tenia asignados se quedaban en su nombre y nadie se
        enteraba hasta que vencian. Aqui se marcan como pendientes de cobertura
        y el aviso va a los agentes disponibles del area del ticket; si el area
        se quedo sin nadie, sube al administrador.

        No reasigna: quien toma el ticket sigue siendo una decision de una
        persona (ServicioTickets.tomar_cobertura), igual que en el resto del
        modelo pull.

        Devuelve la lista de tickets marcados en esta pasada.
        """
        from app.notificaciones_i18n import COBERTURA_REQUERIDA
        from app.services.notificaciones import ServicioNotificaciones

        marcados = []
        for ticket in ServicioDisponibilidad._tickets_vivos_del_agente(usuario.id):
            if ticket.requiere_cobertura:
                continue
            ticket.requiere_cobertura = True
            db.session.add(ticket)
            marcados.append(ticket)

        if not marcados:
            return []

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudieron marcar los tickets para cobertura, error: {e}")
            return []

        for ticket in marcados:
            destinatarios = [
                a for a in ServicioDisponibilidad.agentes_disponibles(ticket.categoria)
                if a.id != usuario.id
            ]
            if not destinatarios:
                destinatarios = ServicioDisponibilidad.admins_activos()
            for destinatario in destinatarios:
                ServicioNotificaciones.crear(
                    usuario_id=destinatario.id,
                    mensaje=COBERTURA_REQUERIDA,
                    ticket_id=ticket.id,
                )

            from app.services.webhooks import ServicioWebhooks
            ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_COBERTURA, ticket, {
                "agente_ausente_id": usuario.id,
            })

        return marcados

    @staticmethod
    def limpiar_cobertura_del_agente(usuario):
        """Quita la marca de cobertura de los tickets que el agente retoma."""
        limpiados = []
        for ticket in ServicioDisponibilidad._tickets_vivos_del_agente(usuario.id):
            if not ticket.requiere_cobertura:
                continue
            ticket.requiere_cobertura = False
            db.session.add(ticket)
            limpiados.append(ticket)

        if not limpiados:
            return []

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo limpiar la marca de cobertura, error: {e}")
            return []

        return limpiados

    @staticmethod
    def marcar_ausente(actor_id, usuario_id, desde=None, hasta=None, motivo=None):
        """Abre una ventana de ausencia para un agente.

        desde nulo significa "desde ahora"; hasta nulo, "hasta nuevo aviso".
        No se cancelan ni se reasignan los tickets que ya tenia: la ausencia
        solo lo saca de las sugerencias, de los destinos de transferencia y del
        conteo de cobertura. Reasignar lo que ya tiene sigue siendo una decision
        humana del administrador.
        """
        usuario = ServicioDisponibilidad._obtener(usuario_id)

        if usuario.rol != RolUsuario.AGENTE:
            raise OperacionNoPermitidaError(_("Solo los agentes tienen estado de disponibilidad"))
        if not usuario.activo:
            raise OperacionNoPermitidaError(_("La cuenta está desactivada"))

        desde = desde or datetime.now()
        if hasta is not None and hasta <= desde:
            raise AusenciaInvalidaError(_("La fecha de regreso debe ser posterior a la de salida"))

        motivo = (motivo or "").strip() or None
        if motivo is not None and len(motivo) > MAX_MOTIVO:
            raise AusenciaInvalidaError(
                _("El motivo no puede superar los %(n)s caracteres", n=MAX_MOTIVO)
            )

        usuario.ausente_desde = desde
        usuario.ausente_hasta = hasta
        usuario.motivo_ausencia = motivo
        ServicioDisponibilidad._guardar(_("No se pudo registrar la ausencia"), usuario)

        if hasta is None:
            detalle = _("Agente %(p1)s ausente desde %(p2)s hasta nuevo aviso",
                        p1=usuario.email, p2=desde.strftime("%d/%m/%Y %H:%M"))
        else:
            detalle = _("Agente %(p1)s ausente del %(p2)s al %(p3)s",
                        p1=usuario.email, p2=desde.strftime("%d/%m/%Y %H:%M"),
                        p3=hasta.strftime("%d/%m/%Y %H:%M"))
        if motivo:
            detalle = f"{detalle} ({motivo})"

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.MARCAR_AUSENTE,
            detalle=detalle,
        )

        # Una ausencia programada para mañana no deja huerfano nada hoy: los
        # tickets se marcan solo cuando la ventana ya esta activa.
        if ServicioDisponibilidad.esta_ausente(usuario):
            ServicioDisponibilidad.marcar_tickets_para_cobertura(usuario)

        return usuario

    @staticmethod
    def marcar_disponible(actor_id, usuario_id):
        """Cierra la ventana de ausencia. Idempotente."""
        usuario = ServicioDisponibilidad._obtener(usuario_id)

        if usuario.rol != RolUsuario.AGENTE:
            raise OperacionNoPermitidaError(_("Solo los agentes tienen estado de disponibilidad"))

        if usuario.ausente_desde is None and usuario.ausente_hasta is None and usuario.motivo_ausencia is None:
            return usuario

        usuario.ausente_desde = None
        usuario.ausente_hasta = None
        usuario.motivo_ausencia = None
        ServicioDisponibilidad._guardar(_("No se pudo registrar el regreso"), usuario)

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.MARCAR_DISPONIBLE,
            detalle=_("Agente %(p1)s marcado como disponible", p1=usuario.email),
        )

        ServicioDisponibilidad.limpiar_cobertura_del_agente(usuario)

        return usuario
