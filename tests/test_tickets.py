"""
Pruebas de ServicioTickets

Que verifica (igual que el script manual original):
1. Un ticket de un usuario NORMAL con texto de Seguridad queda con
   categoria=SEGURIDAD, prioridad=ALTA, y un SLA de ~4 horas.
2. El mismo texto, creado por un usuario VIP, produce la misma categoria
   pero la prioridad se eleva a ALTA (si no lo era ya) y el SLA es el
   corto de VIP (~1.5 horas), no el normal.
3. Un ticket sin ninguna palabra clave conocida cae en OTROS con
   prioridad BAJA, pero si el creador es VIP la prioridad se eleva a ALTA.
4. listar_tickets_por_area reordena los tickets por prioridad (Alta -> Media -> Baja).
5-9. Transiciones de estado (ABIERTO -> EN_PROGRESO, agente obligatorio,
   conflictos de agente, transiciones invalidas, ticket inexistente).
10-13. Reasignacion de agente (valida, ticket inexistente, ticket no en
   progreso, mismo agente).
14-16. Comentarios (valido, ticket inexistente, texto vacio).

Nota de migracion: la contraseña de prueba paso de "ClaveSegura123" a
"ClaveSegura123!" porque validar_politica_contrasena ahora exige un simbolo
(registrar() fallaba con ValueError antes de llegar a nada de lo que prueban
estos tests).
"""
from datetime import datetime

import pytest
from sqlalchemy import select
from app.models.correccion_clasificacion import CorreccionClasificacion
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets, ORDEN_PRIORIDAD
from app.services.exceptions import (
    TransicionInvalidaError, AgenteYaAsignadoError,
    TicketNoEncontradoError, TicketNoEnProgresoError, ComentarioVacioError,ClasificacionYaConfirmadaError
)
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad, EstadoTicket


EMAIL_NORMAL = "prueba_ticket_normal@empresa.com"
EMAIL_VIP = "prueba_ticket_vip@empresa.com"
EMAIL_AGENTE = "prueba_agente@empresa.com"
EMAIL_AGENTE_2 = "prueba_agente_2@empresa.com"
EMAIL_ADMIN_PRUEBA = "prueba_admin@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_NORMAL, EMAIL_VIP, EMAIL_AGENTE, EMAIL_AGENTE_2, EMAIL_ADMIN_PRUEBA):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario VIP",
        email=EMAIL_VIP,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.VIP,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Prueba",
        email=EMAIL_AGENTE,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Prueba 2",
        email=EMAIL_AGENTE_2,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )


def test_ticket_normal_categoria_seguridad():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="alguien entró a mi cuenta, no fui yo",
    )

    assert ticket is not None, "se esperaba que el ticket se creara exitosamente"
    assert ticket.categoria == Categoria.SEGURIDAD, (
        f"se esperaba categoria SEGURIDAD, se obtuvo {ticket.categoria}"
    )
    assert ticket.prioridad == Prioridad.ALTA, (
        f"se esperaba prioridad ALTA, se obtuvo {ticket.prioridad}"
    )

    horas_hasta_limite = (ticket.fecha_limite - datetime.now()).total_seconds() / 3600
    assert 3.5 <= horas_hasta_limite <= 4.5, (
        f"se esperaban ~4 horas de SLA normal, se obtuvo {horas_hasta_limite:.1f}"
    )


def test_ticket_vip_mismo_texto_sla_mas_corto():
    usuario_vip = Usuario.query.filter_by(email=EMAIL_VIP).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_vip,
        texto="alguien entró a mi cuenta, no fui yo",
    )

    assert ticket is not None, "se esperaba que el ticket se creara exitosamente"
    assert ticket.prioridad == Prioridad.ALTA, (
        f"se esperaba prioridad ALTA, se obtuvo {ticket.prioridad}"
    )

    horas_hasta_limite = (ticket.fecha_limite - datetime.now()).total_seconds() / 3600
    assert 1.0 <= horas_hasta_limite <= 2.0, (
        f"se esperaban ~1.5 horas de SLA VIP, se obtuvo {horas_hasta_limite:.1f}"
    )


def test_ticket_vip_categoria_baja_se_eleva_a_alta():
    usuario_vip = Usuario.query.filter_by(email=EMAIL_VIP).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_vip,
        texto="quisiera saber si puedo cambiar el color del tema",
    )

    assert ticket is not None, "se esperaba que el ticket se creara exitosamente"
    assert ticket.categoria == Categoria.OTROS, (
        f"se esperaba categoria OTROS (prioridad base BAJA), se obtuvo {ticket.categoria}"
    )
    assert ticket.prioridad == Prioridad.ALTA, (
        f"siendo VIP, se esperaba que la prioridad se elevara a ALTA, se obtuvo {ticket.prioridad}"
    )


def test_listar_tickets_por_area_ordenados_por_prioridad():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    usuario_vip = Usuario.query.filter_by(email=EMAIL_VIP).first()

    # Software tiene prioridad base BAJA. Creamos primero el de prioridad Baja
    # (usuario normal) y despues el de prioridad Alta (usuario VIP, se eleva),
    # ambos en la misma categoria/area, para confirmar que listar_tickets_por_area
    # de verdad reordena y no solo devuelve el orden de inserción.
    ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="el programa de facturación se cierra solo",  # Software -> BAJA
    )
    ServicioTickets.crear_ticket(
        creador=usuario_vip,
        texto="no abre el programa de nomina",  # Software -> BAJA, pero VIP -> se eleva a ALTA
    )

    tickets_del_area = ServicioTickets.listar_tickets_por_area(Categoria.SOFTWARE)

    assert len(tickets_del_area) >= 2, (
        f"se esperaban al menos 2 tickets en Software, se obtuvieron {len(tickets_del_area)}"
    )

    prioridades_obtenidas = [t.prioridad for t in tickets_del_area]

    assert Prioridad.ALTA in prioridades_obtenidas and Prioridad.BAJA in prioridades_obtenidas, (
        f"la prueba necesita prioridades mixtas para validar el orden, se obtuvo {prioridades_obtenidas}"
    )

    prioridades_ordenadas = sorted(prioridades_obtenidas, key=lambda p: ORDEN_PRIORIDAD[p])
    assert prioridades_obtenidas == prioridades_ordenadas, (
        f"la lista no vino ordenada por prioridad: {prioridades_obtenidas}"
    )


def test_cambiar_estado_abierto_a_en_progreso():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    estado = ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )

    assert estado == EstadoTicket.EN_PROGRESO, (
        f"se esperaba EN_PROGRESO exitoso, se obtuvo estado={estado}"
    )


def test_cambiar_estado_sin_agente_falla():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    with pytest.raises(TransicionInvalidaError):
        ServicioTickets.cambiar_estado(
            ticket_id=ticket.id,
            nuevo_estado=EstadoTicket.EN_PROGRESO,
            actor_id=agente.id,
            agente_id=None,
        )


def test_cambiar_estado_agente_en_conflicto():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )

    otro_agente_id = agente.id + 1  # id distinto, no necesita existir para esta prueba de conflicto

    with pytest.raises(TransicionInvalidaError):
        ServicioTickets.cambiar_estado(
            ticket_id=ticket.id,
            nuevo_estado=EstadoTicket.EN_PROGRESO,
            actor_id=agente.id,
            agente_id=otro_agente_id,
        )


def test_cambiar_estado_transicion_invalida():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )

    with pytest.raises(TransicionInvalidaError):
        ServicioTickets.cambiar_estado(
            ticket_id=ticket.id,
            nuevo_estado=EstadoTicket.ABIERTO,
            actor_id=agente.id,
        )


def test_cambiar_estado_ticket_inexistente():
    with pytest.raises(TicketNoEncontradoError):
        ServicioTickets.cambiar_estado(
            ticket_id=999999,
            nuevo_estado=EstadoTicket.EN_PROGRESO,
            actor_id=1,
            agente_id=1,
        )


def test_reasignar_agente_valido():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()
    admin_prueba = Usuario.query.filter_by(email=EMAIL_ADMIN_PRUEBA).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente_1.id,
        agente_id=agente_1.id,
    )

    agente_resultante = ServicioTickets.reasignar_agente(
        ticket_id=ticket.id,
        nuevo_agente_id=agente_2.id,
        actor_id=admin_prueba.id,
    )

    assert agente_resultante == agente_2.id, (
        f"se esperaba reasignacion exitosa a agente_2, se obtuvo agente={agente_resultante}"
    )


def test_reasignar_agente_ticket_inexistente():
    with pytest.raises(TicketNoEncontradoError):
        ServicioTickets.reasignar_agente(
            ticket_id=999999,
            nuevo_agente_id=1,
            actor_id=1,
        )


def test_reasignar_agente_ticket_no_en_progreso():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()
    admin_prueba = Usuario.query.filter_by(email=EMAIL_ADMIN_PRUEBA).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    # ticket recien creado queda en ABIERTO, nunca paso por cambiar_estado

    with pytest.raises(TicketNoEnProgresoError):
        ServicioTickets.reasignar_agente(
            ticket_id=ticket.id,
            nuevo_agente_id=agente_2.id,
            actor_id=admin_prueba.id,
        )


def test_reasignar_agente_mismo_agente():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin_prueba = Usuario.query.filter_by(email=EMAIL_ADMIN_PRUEBA).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente_1.id,
        agente_id=agente_1.id,
    )

    with pytest.raises(AgenteYaAsignadoError):
        ServicioTickets.reasignar_agente(
            ticket_id=ticket.id,
            nuevo_agente_id=agente_1.id,
            actor_id=admin_prueba.id,
        )


def test_agregar_comentario_valido():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    comentario = ServicioTickets.agregar_comentario(
        ticket_id=ticket.id,
        autor_id=agente_1.id,
        texto="Estamos revisando tu caso, te contactaremos pronto.",
    )

    assert comentario is not None, "se esperaba que el comentario se creara exitosamente"
    assert comentario.ticket_id == ticket.id and comentario.autor_id == agente_1.id, (
        f"ticket_id o autor_id no coinciden, se obtuvo ticket_id={comentario.ticket_id}, "
        f"autor_id={comentario.autor_id}"
    )


def test_agregar_comentario_ticket_inexistente():
    with pytest.raises(TicketNoEncontradoError):
        ServicioTickets.agregar_comentario(
            ticket_id=999999,
            autor_id=1,
            texto="comentario sobre ticket que no existe",
        )


def test_agregar_comentario_texto_vacio():
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    with pytest.raises(ComentarioVacioError):
        ServicioTickets.agregar_comentario(
            ticket_id=ticket.id,
            autor_id=usuario_normal.id,
            texto="   ",
        )
"""
Pruebas de ServicioTickets.confirmar_clasificacion y
listar_pendientes_revision_clasificacion (agregar al final de test_tickets.py)

Que verifica:
1. confirmar_clasificacion: caso valido -- cambia la categoria y apaga
   clasificacion_baja_confianza.
2. confirmar_clasificacion: ticket inexistente -> TicketNoEncontradoError.
3. confirmar_clasificacion: ticket que NO esta en baja confianza (ya
   confirmado o nunca lo estuvo) -> ClasificacionYaConfirmadaError.
4. listar_pendientes_revision_clasificacion: solo trae los que tienen
   clasificacion_baja_confianza=True, ordenados por fecha_creacion
   (mas viejo primero).
5. listar_pendientes_revision_clasificacion: vacio si no hay ninguno
   pendiente.

Nota: crear_ticket() en el entorno de tests usa el clasificador simple
(CLASIFICADOR_ML_ACTIVO=False por defecto), que nunca marca
clasificacion_baja_confianza=True -- por eso estas pruebas fuerzan el
campo directo por SQLAlchemy despues de crear el ticket, mismo patron ya
usado en las pruebas de SLA (forzar fecha_limite) y de condiciones de
carrera (forzar estado directo).
"""



EMAIL_CLASIF_ADMIN = "prueba_clasif_admin@empresa.com"
EMAIL_CLASIF_NORMAL = "prueba_clasif_normal@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_confirmar_clasificacion():
    for email in (EMAIL_CLASIF_ADMIN, EMAIL_CLASIF_NORMAL):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Clasificacion",
        email=EMAIL_CLASIF_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Clasificacion", email=EMAIL_CLASIF_NORMAL,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )


def _crear_ticket_baja_confianza(creador):
    """Helper local: crea un ticket normal y fuerza clasificacion_baja_confianza=True
    directo por SQLAlchemy -- el clasificador simple de los tests nunca
    produce ese estado por si solo."""
    ticket = ServicioTickets.crear_ticket(creador=creador, texto="texto cualquiera para la prueba")
    ticket.clasificacion_baja_confianza = True
    db.session.add(ticket)
    db.session.commit()
    return ticket


# ---------------------------------------------------------------------------
# confirmar_clasificacion
# ---------------------------------------------------------------------------

def test_confirmar_clasificacion_valido():
    normal = Usuario.query.filter_by(email=EMAIL_CLASIF_NORMAL).first()
    admin = Usuario.query.filter_by(email=EMAIL_CLASIF_ADMIN).first()

    ticket = _crear_ticket_baja_confianza(normal)

    resultado = ServicioTickets.confirmar_clasificacion(ticket.id, Categoria.REDES, admin.id)

    assert resultado.categoria == Categoria.REDES, (
        f"se esperaba categoria REDES tras confirmar, se obtuvo {resultado.categoria}"
    )
    assert resultado.clasificacion_baja_confianza is False, (
        "tras confirmar, clasificacion_baja_confianza debe quedar en False"
    )

def test_confirmar_clasificacion_crea_correccion():
    normal = Usuario.query.filter_by(email=EMAIL_CLASIF_NORMAL).first()
    admin = Usuario.query.filter_by(email=EMAIL_CLASIF_ADMIN).first()

    ticket = _crear_ticket_baja_confianza(normal)
    categoria_antes_de_confirmar = ticket.categoria

    ServicioTickets.confirmar_clasificacion(ticket.id, Categoria.REDES, admin.id)

    correccion = db.session.execute(
        select(CorreccionClasificacion).where(CorreccionClasificacion.ticket_id == ticket.id)
    ).scalar()

    assert correccion is not None, "deberia haberse creado una fila en CorreccionClasificacion"
    assert correccion.categoria_original == categoria_antes_de_confirmar
    assert correccion.categoria_correcta == Categoria.REDES
    assert correccion.texto == ticket.texto
    assert correccion.actor_id == admin.id
    
def test_confirmar_clasificacion_ticket_inexistente():
    admin = Usuario.query.filter_by(email=EMAIL_CLASIF_ADMIN).first()

    with pytest.raises(TicketNoEncontradoError):
        ServicioTickets.confirmar_clasificacion(999999, Categoria.REDES, admin.id)


def test_confirmar_clasificacion_ya_confirmada():
    normal = Usuario.query.filter_by(email=EMAIL_CLASIF_NORMAL).first()
    admin = Usuario.query.filter_by(email=EMAIL_CLASIF_ADMIN).first()

    # Ticket normal, creado sin forzar baja_confianza -- nunca estuvo pendiente
    ticket = ServicioTickets.crear_ticket(creador=normal, texto="ticket normal sin baja confianza")

    with pytest.raises(ClasificacionYaConfirmadaError):
        ServicioTickets.confirmar_clasificacion(ticket.id, Categoria.REDES, admin.id)


# ---------------------------------------------------------------------------
# listar_pendientes_revision_clasificacion
# ---------------------------------------------------------------------------

def test_listar_pendientes_revision_clasificacion():
    normal = Usuario.query.filter_by(email=EMAIL_CLASIF_NORMAL).first()

    ticket_pendiente_1 = _crear_ticket_baja_confianza(normal)
    ticket_pendiente_2 = _crear_ticket_baja_confianza(normal)
    ticket_normal = ServicioTickets.crear_ticket(creador=normal, texto="este no deberia aparecer")

    pendientes = ServicioTickets.listar_pendientes_revision_clasificacion()
    ids_pendientes = [t.id for t in pendientes]

    assert ticket_pendiente_1.id in ids_pendientes, "el primer ticket pendiente deberia aparecer en la lista"
    assert ticket_pendiente_2.id in ids_pendientes, "el segundo ticket pendiente deberia aparecer en la lista"
    assert ticket_normal.id not in ids_pendientes, (
        "un ticket sin clasificacion_baja_confianza no deberia aparecer en la lista"
    )

    # Orden: el mas viejo primero
    posicion_1 = ids_pendientes.index(ticket_pendiente_1.id)
    posicion_2 = ids_pendientes.index(ticket_pendiente_2.id)
    assert posicion_1 < posicion_2, (
        "se esperaba que el ticket creado primero apareciera antes en la lista"
    )


def test_listar_pendientes_revision_clasificacion_vacio():
    normal = Usuario.query.filter_by(email=EMAIL_CLASIF_NORMAL).first()

    # Confirmar cualquier pendiente que haya quedado de tests anteriores en este archivo
    pendientes_previos = ServicioTickets.listar_pendientes_revision_clasificacion()
    for t in pendientes_previos:
        t.clasificacion_baja_confianza = False
        db.session.add(t)
    db.session.commit()

    pendientes = ServicioTickets.listar_pendientes_revision_clasificacion()
    assert pendientes == [], f"se esperaba lista vacia, se obtuvo {len(pendientes)} pendientes"