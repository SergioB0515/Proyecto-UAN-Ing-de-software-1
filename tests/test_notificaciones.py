"""
Pruebas de ServicioNotificaciones

PARTE 1 -- servicio aislado (crear, poda, listar, contar, marcar leida):
1. crear: caso valido (guarda con leida=False por defecto).
2. crear: poda automatica -- al superar LIMITE_POR_USUARIO (15), se borra
   la mas vieja y se conserva exactamente 15.
3. crear: la poda es por usuario.
4. listar_para_usuario: orden mas reciente primero, solo las de ese usuario.
5. contar_no_leidas: cuenta solo las no leidas, solo las de ese usuario.
6-8. marcar_leida: valido, inexistente, de otro usuario.
9. marcar_todas_leidas: marca solo las del usuario dado, no toca otras.

PARTE 2 -- integracion con los servicios de negocio reales (los "enganches"):
verifica que cada accion real dispara la notificacion correcta, comparando
contra las CONSTANTES de app.notificaciones_i18n (no contra texto
interpolado -- Notificacion.mensaje guarda la plantilla cruda sin
resolver, la interpolacion del ticket_id ocurre despues, en render()).

10. crear_solicitud -> notif.TRANSFERENCIA_NUEVA al agente destino.
11. aceptar_solicitud -> notif.TRANSFERENCIA_ACEPTADA al solicitante.
12. rechazar_solicitud -> notif.TRANSFERENCIA_RECHAZADA al solicitante.
13. escalar_a_area -> notif.ESCALAMIENTO_PENDIENTE a TODOS los admins (fan-out).
14. aprobar_escalamiento -> notif.ESCALAMIENTO_APROBADO al solicitante.
15. rechazar_escalamiento -> notif.ESCALAMIENTO_RECHAZADO al solicitante.
16. cambiar_prioridad -> notif.PRIORIDAD_PENDIENTE a TODOS los admins (fan-out).
17. aprobar_cambio_prioridad -> notif.PRIORIDAD_APROBADO al solicitante.
18. rechazar_cambio_prioridad -> notif.PRIORIDAD_RECHAZADO al solicitante.
19. cambiar_estado a CERRADO desde EN_PROGRESO -> notif.CERRADO al creador.
20. cambiar_estado a CERRADO desde ABIERTO (cierre directo) -> notif.CERRADO_SIN_ATENDER.
21. cambiar_estado a EN_PROGRESO (solo tomar) -> NO genera ninguna notificacion (caso negativo).

Nota: "no puedo entrar a mi correo" clasifica como PERMISOS.
"""
import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.notificaciones import ServicioNotificaciones
from app import notificaciones_i18n as notif
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.notificacion import Notificacion
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, Prioridad


EMAIL_ADMIN = "prueba_notificaciones_admin@empresa.com"
EMAIL_USUARIO_A = "prueba_notificaciones_a@empresa.com"
EMAIL_USUARIO_B = "prueba_notificaciones_b@empresa.com"

EMAIL_ADMIN_2 = "prueba_notificaciones_admin2@empresa.com"
EMAIL_NORMAL = "prueba_notificaciones_normal@empresa.com"
EMAIL_AGENTE_ORIGEN = "prueba_notificaciones_agente_origen@empresa.com"
EMAIL_AGENTE_DESTINO = "prueba_notificaciones_agente_destino@empresa.com"

TEXTO_TICKET_PERMISOS = "no puedo entrar a mi correo"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_USUARIO_A, EMAIL_USUARIO_B, EMAIL_ADMIN_2,
                  EMAIL_NORMAL, EMAIL_AGENTE_ORIGEN, EMAIL_AGENTE_DESTINO):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Notificaciones",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Notificaciones A", email=EMAIL_USUARIO_A, contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL, nivel=NivelUsuario.NORMAL, admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario Notificaciones B", email=EMAIL_USUARIO_B, contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL, nivel=NivelUsuario.NORMAL, admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Admin Prueba Notificaciones 2", email=EMAIL_ADMIN_2, contrasena="ClaveSegura123!",
        rol=RolUsuario.ADMIN, nivel=NivelUsuario.NORMAL, admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Notificaciones", email=EMAIL_NORMAL, contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL, nivel=NivelUsuario.NORMAL, admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Origen Notificaciones", email=EMAIL_AGENTE_ORIGEN, contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE, nivel=NivelUsuario.NORMAL, admin_id=admin_prueba.id, area_soporte=Categoria.PERMISOS,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Destino Notificaciones", email=EMAIL_AGENTE_DESTINO, contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE, nivel=NivelUsuario.NORMAL, admin_id=admin_prueba.id, area_soporte=Categoria.PERMISOS,
    )


def _limpiar_notificaciones(usuario_id):
    """Helper local: borra cualquier notificacion previa de ese usuario,
    para que cada test que dependa de un conteo exacto empiece en cero."""
    db.session.query(Notificacion).filter(Notificacion.usuario_id == usuario_id).delete()
    db.session.commit()


def _plantillas_de(usuario_id):
    """Helper local: devuelve solo las plantillas (Notificacion.mensaje) de
    un usuario -- comparar contra estas, no contra texto interpolado, ya
    que mensaje guarda la constante cruda de notificaciones_i18n."""
    return [n.mensaje for n in ServicioNotificaciones.listar_para_usuario(usuario_id)]


def _crear_ticket_en_progreso(creador, agente):
    ticket = ServicioTickets.crear_ticket(creador=creador, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    return ticket


# ===========================================================================
# PARTE 1 -- ServicioNotificaciones aislado
# ===========================================================================

def test_crear_valido():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Notificacion de prueba")

    notificaciones = ServicioNotificaciones.listar_para_usuario(usuario_a.id)
    assert len(notificaciones) == 1, f"se esperaba 1 notificacion, se obtuvieron {len(notificaciones)}"
    assert notificaciones[0].leida is False, "una notificacion recien creada debe empezar como no leida"
    assert notificaciones[0].mensaje == "Notificacion de prueba", (
        f"mensaje incorrecto, se obtuvo '{notificaciones[0].mensaje}'"
    )


def test_crear_poda_al_superar_el_limite():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    for i in range(16):
        ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje=f"Mensaje {i}")

    notificaciones = ServicioNotificaciones.listar_para_usuario(usuario_a.id)

    assert len(notificaciones) == ServicioNotificaciones.LIMITE_POR_USUARIO, (
        f"se esperaban exactamente {ServicioNotificaciones.LIMITE_POR_USUARIO} notificaciones, "
        f"se obtuvieron {len(notificaciones)}"
    )
    mensajes = {n.mensaje for n in notificaciones}
    assert "Mensaje 0" not in mensajes, "la notificacion mas antigua deberia haber sido podada"
    assert "Mensaje 15" in mensajes, "la notificacion mas reciente deberia seguir presente"


def test_crear_poda_es_por_usuario():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    usuario_b = Usuario.query.filter_by(email=EMAIL_USUARIO_B).first()
    _limpiar_notificaciones(usuario_a.id)
    _limpiar_notificaciones(usuario_b.id)

    for i in range(16):
        ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje=f"A-{i}")
    ServicioNotificaciones.crear(usuario_id=usuario_b.id, mensaje="B-unica")

    notificaciones_b = ServicioNotificaciones.listar_para_usuario(usuario_b.id)
    assert len(notificaciones_b) == 1, (
        f"la poda de A no deberia afectar a B, se obtuvieron {len(notificaciones_b)}"
    )


def test_listar_para_usuario_orden_mas_reciente_primero():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Primera")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Segunda")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Tercera")

    notificaciones = ServicioNotificaciones.listar_para_usuario(usuario_a.id)
    assert notificaciones[0].mensaje == "Tercera", f"se esperaba 'Tercera' primero, se obtuvo '{notificaciones[0].mensaje}'"
    assert notificaciones[-1].mensaje == "Primera", f"se esperaba 'Primera' ultima, se obtuvo '{notificaciones[-1].mensaje}'"


def test_contar_no_leidas():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="No leida 1")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="No leida 2")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Esta se marca leida")

    notificaciones = ServicioNotificaciones.listar_para_usuario(usuario_a.id)
    ServicioNotificaciones.marcar_leida(notificaciones[0].id, usuario_a.id)

    contador = ServicioNotificaciones.contar_no_leidas(usuario_a.id)
    assert contador == 2, f"se esperaban 2 no leidas, se obtuvo {contador}"


def test_contar_no_leidas_es_por_usuario():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    usuario_b = Usuario.query.filter_by(email=EMAIL_USUARIO_B).first()
    _limpiar_notificaciones(usuario_a.id)
    _limpiar_notificaciones(usuario_b.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="De A")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="De A tambien")

    contador_b = ServicioNotificaciones.contar_no_leidas(usuario_b.id)
    assert contador_b == 0, f"las notificaciones de A no deberian contar para B, se obtuvo {contador_b}"


def test_marcar_leida_valido():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Para marcar")
    notificacion = ServicioNotificaciones.listar_para_usuario(usuario_a.id)[0]

    resultado = ServicioNotificaciones.marcar_leida(notificacion.id, usuario_a.id)
    assert resultado is not None, "se esperaba que devolviera la notificacion actualizada"
    assert resultado.leida is True, "se esperaba leida=True tras marcarla"


def test_marcar_leida_inexistente_no_truena():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    resultado = ServicioNotificaciones.marcar_leida(999999, usuario_a.id)
    assert resultado is None, "una notificacion inexistente debe devolver None, no lanzar excepcion"


def test_marcar_leida_de_otro_usuario_no_la_toca():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    usuario_b = Usuario.query.filter_by(email=EMAIL_USUARIO_B).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Es de A, no de B")
    notificacion_de_a = ServicioNotificaciones.listar_para_usuario(usuario_a.id)[0]

    resultado = ServicioNotificaciones.marcar_leida(notificacion_de_a.id, usuario_b.id)
    assert resultado is None, "usuario B no deberia poder marcar como leida una notificacion de A"

    notificacion_sin_tocar = db.session.get(Notificacion, notificacion_de_a.id)
    assert notificacion_sin_tocar.leida is False, "el intento de B no debio modificar la notificacion real de A"


def test_marcar_todas_leidas():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    usuario_b = Usuario.query.filter_by(email=EMAIL_USUARIO_B).first()
    _limpiar_notificaciones(usuario_a.id)
    _limpiar_notificaciones(usuario_b.id)

    for i in range(3):
        ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje=f"A-{i}")
    ServicioNotificaciones.crear(usuario_id=usuario_b.id, mensaje="B-sigue-no-leida")

    marcadas = ServicioNotificaciones.marcar_todas_leidas(usuario_a.id)

    assert marcadas == 3, f"se esperaban 3 marcadas, se obtuvo {marcadas}"
    assert ServicioNotificaciones.contar_no_leidas(usuario_a.id) == 0, "A no debe tener notificaciones sin leer"
    assert ServicioNotificaciones.contar_no_leidas(usuario_b.id) == 1, "marcar todas de A no debe tocar las de B"


# ===========================================================================
# PARTE 2 -- Integracion con los servicios de negocio reales
# ===========================================================================

def test_notificacion_al_crear_solicitud_transferencia():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()
    _limpiar_notificaciones(destino.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    assert notif.TRANSFERENCIA_NUEVA in _plantillas_de(destino.id), (
        "se esperaba notif.TRANSFERENCIA_NUEVA para el agente destino"
    )


def test_notificacion_al_aceptar_solicitud():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()
    _limpiar_notificaciones(origen.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )
    ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud.id, destino.id)

    assert notif.TRANSFERENCIA_ACEPTADA in _plantillas_de(origen.id), (
        "se esperaba notif.TRANSFERENCIA_ACEPTADA para el solicitante"
    )


def test_notificacion_al_rechazar_solicitud():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()
    _limpiar_notificaciones(origen.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )
    ServicioSolicitudesTransferencia.rechazar_solicitud(solicitud.id, destino.id)

    assert notif.TRANSFERENCIA_RECHAZADA in _plantillas_de(origen.id), (
        "se esperaba notif.TRANSFERENCIA_RECHAZADA para el solicitante"
    )


def test_notificacion_al_escalar_llega_a_todos_los_admins():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    admin_2 = Usuario.query.filter_by(email=EMAIL_ADMIN_2).first()
    _limpiar_notificaciones(admin.id)
    _limpiar_notificaciones(admin_2.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.SEGURIDAD, solicitante_id=origen.id, motivo="Es de seguridad",
    )

    assert notif.ESCALAMIENTO_PENDIENTE in _plantillas_de(admin.id), "admin deberia ser notificado"
    assert notif.ESCALAMIENTO_PENDIENTE in _plantillas_de(admin_2.id), "admin_2 tambien (fan-out a TODOS)"


def test_notificacion_al_aprobar_escalamiento():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    _limpiar_notificaciones(origen.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES, solicitante_id=origen.id, motivo="Es de red",
    )
    ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud.id, admin.id)

    assert notif.ESCALAMIENTO_APROBADO in _plantillas_de(origen.id), (
        "se esperaba notif.ESCALAMIENTO_APROBADO para el solicitante"
    )


def test_notificacion_al_rechazar_escalamiento():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    _limpiar_notificaciones(origen.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES, solicitante_id=origen.id, motivo="Es de red",
    )
    ServicioSolicitudesTransferencia.rechazar_escalamiento(solicitud.id, admin.id)

    assert notif.ESCALAMIENTO_RECHAZADO in _plantillas_de(origen.id), (
        "se esperaba notif.ESCALAMIENTO_RECHAZADO para el solicitante"
    )


def test_notificacion_al_cambiar_prioridad_llega_a_todos_los_admins():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    admin_2 = Usuario.query.filter_by(email=EMAIL_ADMIN_2).first()
    _limpiar_notificaciones(admin.id)
    _limpiar_notificaciones(admin_2.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA, solicitante_id=origen.id, motivo="Urgente",
    )

    assert notif.PRIORIDAD_PENDIENTE in _plantillas_de(admin.id), "admin deberia ser notificado"
    assert notif.PRIORIDAD_PENDIENTE in _plantillas_de(admin_2.id), "admin_2 tambien (fan-out a TODOS)"


def test_notificacion_al_aprobar_cambio_prioridad():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    _limpiar_notificaciones(origen.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA, solicitante_id=origen.id, motivo="Urgente",
    )
    ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud.id, admin.id)

    assert notif.PRIORIDAD_APROBADO in _plantillas_de(origen.id), (
        "se esperaba notif.PRIORIDAD_APROBADO para el solicitante"
    )


def test_notificacion_al_rechazar_cambio_prioridad():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    _limpiar_notificaciones(origen.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA, solicitante_id=origen.id, motivo="Urgente",
    )
    ServicioSolicitudesTransferencia.rechazar_cambio_prioridad(solicitud.id, admin.id)

    assert notif.PRIORIDAD_RECHAZADO in _plantillas_de(origen.id), (
        "se esperaba notif.PRIORIDAD_RECHAZADO para el solicitante"
    )


def test_notificacion_al_cerrar_ticket_desde_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    _limpiar_notificaciones(normal.id)

    ticket = _crear_ticket_en_progreso(normal, origen)
    ServicioTickets.cambiar_estado(ticket_id=ticket.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=origen.id)

    assert notif.CERRADO in _plantillas_de(normal.id), "se esperaba notif.CERRADO (cierre normal, no directo)"
    assert notif.CERRADO_SIN_ATENDER not in _plantillas_de(normal.id), (
        "un cierre normal NO debe usar la plantilla de cierre directo"
    )


def test_notificacion_al_cerrar_ticket_directo_desde_abierto():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    _limpiar_notificaciones(normal.id)

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)  # queda ABIERTO
    ServicioTickets.cambiar_estado(ticket_id=ticket.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=origen.id)

    assert notif.CERRADO_SIN_ATENDER in _plantillas_de(normal.id), (
        "un cierre directo desde ABIERTO debe usar notif.CERRADO_SIN_ATENDER"
    )


def test_no_hay_notificacion_al_solo_tomar_el_ticket():
    """Caso negativo: pasar de ABIERTO a EN_PROGRESO (tomar el ticket) no
    debe generar ninguna notificacion -- el guard esta acotado a CERRADO."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    _limpiar_notificaciones(normal.id)

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO, actor_id=origen.id, agente_id=origen.id,
    )

    assert _plantillas_de(normal.id) == [], "tomar un ticket no deberia generar ninguna notificacion"