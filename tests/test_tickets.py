"""
Script de prueba manual para ServicioTickets.crear_ticket()

Como correrlo (desde la carpeta Proyecto, con el entorno virtual activado):
    python -m tests.test_tickets

Que verifica:
1. Un ticket de un usuario NORMAL con texto de Seguridad queda con
   categoria=SEGURIDAD, prioridad=ALTA, y un SLA de ~4 horas.
2. El mismo texto, creado por un usuario VIP, produce el mismo categoria
   pero la prioridad se eleva a ALTA (si no lo era ya) y el SLA es el
   corto de VIP (~1.5 horas), no el normal.
3. Un ticket sin ninguna palabra clave conocida cae en OTROS con
   prioridad BAJA.
"""
from app.services.exceptions import TransicionInvalidaError, AgenteYaAsignadoError, TicketNoEncontradoError, TicketNoEnProgresoError
from datetime import datetime
from app.services.tickets import ServicioTickets, ORDEN_PRIORIDAD
from app.models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad, EstadoTicket
from app.services.exceptions import TransicionInvalidaError, AgenteYaAsignadoError, TicketNoEncontradoError
from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets, ORDEN_PRIORIDAD
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad
from app.services.exceptions import (
    TransicionInvalidaError, AgenteYaAsignadoError,
    TicketNoEncontradoError, TicketNoEnProgresoError, ComentarioVacioError
)

EMAIL_AGENTE_2 = "prueba_agente_2@empresa.com"
EMAIL_NORMAL = "prueba_ticket_normal@empresa.com"
EMAIL_VIP = "prueba_ticket_vip@empresa.com"
EMAIL_AGENTE = "prueba_agente@empresa.com"
EMAIL_ADMIN_PRUEBA = "prueba_admin@empresa.com"
def preparar_usuarios_de_prueba():
    for email in (EMAIL_NORMAL, EMAIL_VIP, EMAIL_AGENTE, EMAIL_AGENTE_2, EMAIL_ADMIN_PRUEBA):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario VIP",
        email=EMAIL_VIP,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.VIP,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Prueba",
        email=EMAIL_AGENTE,
        contrasena="ClaveSegura123",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Prueba 2",
        email=EMAIL_AGENTE_2,
        contrasena="ClaveSegura123",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )


def test_ticket_normal_categoria_seguridad():
    print("\n--- Prueba 1: ticket de Seguridad, usuario normal ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    exito, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="alguien entró a mi cuenta, no fui yo",
    )

    if not exito or ticket is None:
        print("FALLO: se esperaba que el ticket se creara exitosamente")
        return

    if ticket.categoria != Categoria.SEGURIDAD:
        print(f"FALLO: se esperaba categoria SEGURIDAD, se obtuvo {ticket.categoria}")
        return

    if ticket.prioridad != Prioridad.ALTA:
        print(f"FALLO: se esperaba prioridad ALTA, se obtuvo {ticket.prioridad}")
        return

    horas_hasta_limite = (ticket.fecha_limite - datetime.now()).total_seconds() / 3600
    print(f"  categoria={ticket.categoria}, prioridad={ticket.prioridad}, horas hasta el limite={horas_hasta_limite:.1f}")

    if not (3.5 <= horas_hasta_limite <= 4.5):
        print(f"FALLO: se esperaban ~4 horas de SLA normal, se obtuvo {horas_hasta_limite:.1f}")
        return

    print("OK: ticket normal clasificado y con SLA de ~4 horas")


def test_ticket_vip_mismo_texto_sla_mas_corto():
    print("\n--- Prueba 2: mismo texto, usuario VIP -> SLA mas corto ---")
    usuario_vip = Usuario.query.filter_by(email=EMAIL_VIP).first()

    exito, ticket = ServicioTickets.crear_ticket(
        creador=usuario_vip,
        texto="alguien entró a mi cuenta, no fui yo",
    )

    if not exito or ticket is None:
        print("FALLO: se esperaba que el ticket se creara exitosamente")
        return

    if ticket.prioridad != Prioridad.ALTA:
        print(f"FALLO: se esperaba prioridad ALTA, se obtuvo {ticket.prioridad}")
        return

    horas_hasta_limite = (ticket.fecha_limite - datetime.now()).total_seconds() / 3600
    print(f"  prioridad={ticket.prioridad}, horas hasta el limite={horas_hasta_limite:.1f}")

    if not (1.0 <= horas_hasta_limite <= 2.0):
        print(f"FALLO: se esperaban ~1.5 horas de SLA VIP, se obtuvo {horas_hasta_limite:.1f}")
        return

    print("OK: ticket VIP con SLA acelerado de ~1.5 horas")


def test_ticket_vip_categoria_baja_se_eleva_a_alta():
    print("\n--- Prueba 3: usuario VIP con categoria de prioridad base BAJA -> se eleva a ALTA ---")
    usuario_vip = Usuario.query.filter_by(email=EMAIL_VIP).first()

    exito, ticket = ServicioTickets.crear_ticket(
        creador=usuario_vip,
        texto="quisiera saber si puedo cambiar el color del tema",
    )

    if not exito or ticket is None:
        print("FALLO: se esperaba que el ticket se creara exitosamente")
        return

    if ticket.categoria != Categoria.OTROS:
        print(f"FALLO: se esperaba categoria OTROS (prioridad base BAJA), se obtuvo {ticket.categoria}")
        return

    if ticket.prioridad != Prioridad.ALTA:
        print(f"FALLO: siendo VIP, se esperaba que la prioridad se elevara a ALTA, se obtuvo {ticket.prioridad}")
        return

    print("OK: la prioridad base BAJA se elevo a ALTA por ser el creador VIP")


def test_listar_tickets_por_area_ordenados_por_prioridad():
    print("\n--- Prueba 4: listar tickets por area, ordenados Alta -> Media -> Baja ---")
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

    if len(tickets_del_area) < 2:
        print(f"FALLO: se esperaban al menos 2 tickets en Software, se obtuvieron {len(tickets_del_area)}")
        return

    prioridades_obtenidas = [t.prioridad for t in tickets_del_area]

    if Prioridad.ALTA not in prioridades_obtenidas or Prioridad.BAJA not in prioridades_obtenidas:
        print(f"FALLO: la prueba necesita prioridades mixtas para validar el orden, se obtuvo {prioridades_obtenidas}")
        return

    prioridades_ordenadas = sorted(prioridades_obtenidas, key=lambda p: ORDEN_PRIORIDAD[p])

    if prioridades_obtenidas != prioridades_ordenadas:
        print(f"FALLO: la lista no vino ordenada por prioridad: {prioridades_obtenidas}")
        return

    print(f"OK: {len(tickets_del_area)} tickets de Software, con prioridades mixtas, orden correcto: {prioridades_obtenidas}")
def test_cambiar_estado_abierto_a_en_progreso():
    print("\n--- Prueba 5: ABIERTO -> EN_PROGRESO con agente_id valido ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    exito, estado = ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )

    if not exito or estado != EstadoTicket.EN_PROGRESO:
        print(f"FALLO: se esperaba EN_PROGRESO exitoso, se obtuvo exito={exito}, estado={estado}")
        return

    print("OK: ABIERTO -> EN_PROGRESO con agente asignado correctamente")


def test_cambiar_estado_sin_agente_falla():
    print("\n--- Prueba 6: ABIERTO -> EN_PROGRESO sin agente_id debe fallar ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    try:
        ServicioTickets.cambiar_estado(
            ticket_id=ticket.id,
            nuevo_estado=EstadoTicket.EN_PROGRESO,
            actor_id=agente.id,
            agente_id=None,
        )
        print("FALLO: se esperaba TransicionInvalidaError por falta de agente_id")
    except TransicionInvalidaError:
        print("OK: fallo correctamente por falta de agente_id")


def test_cambiar_estado_agente_en_conflicto():
    print("\n--- Prueba 7: reasignar agente distinto al ya asignado debe fallar ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    _, ticket = ServicioTickets.crear_ticket(
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

    try:
        ServicioTickets.cambiar_estado(
            ticket_id=ticket.id,
            nuevo_estado=EstadoTicket.EN_PROGRESO,
            actor_id=agente.id,
            agente_id=otro_agente_id,
        )
        print("FALLO: se esperaba TransicionInvalidaError")
    except TransicionInvalidaError:
        print("OK: fallo correctamente, EN_PROGRESO->EN_PROGRESO no es transicion valida")


def test_cambiar_estado_transicion_invalida():
    print("\n--- Prueba 8: EN_PROGRESO -> ABIERTO debe fallar (transicion no permitida) ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )

    try:
        ServicioTickets.cambiar_estado(
            ticket_id=ticket.id,
            nuevo_estado=EstadoTicket.ABIERTO,
            actor_id=agente.id,
        )
        print("FALLO: se esperaba TransicionInvalidaError")
    except TransicionInvalidaError:
        print("OK: fallo correctamente, EN_PROGRESO -> ABIERTO bloqueado")


def test_cambiar_estado_ticket_inexistente():
    print("\n--- Prueba 9: ticket_id inexistente debe lanzar TicketNoEncontradoError ---")
    try:
        ServicioTickets.cambiar_estado(
            ticket_id=999999,
            nuevo_estado=EstadoTicket.EN_PROGRESO,
            actor_id=1,
            agente_id=1,
        )
        print("FALLO: se esperaba TicketNoEncontradoError")
    except TicketNoEncontradoError:
        print("OK: fallo correctamente, ticket inexistente detectado")

def test_reasignar_agente_valido():
    print("\n--- Prueba 10: reasignar agente sobre ticket EN_PROGRESO ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente_1.id,
        agente_id=agente_1.id,
    )

    exito, agente_resultante = ServicioTickets.reasignar_agente(
        ticket_id=ticket.id,
        nuevo_agente_id=agente_2.id,
    )

    if not exito or agente_resultante != agente_2.id:
        print(f"FALLO: se esperaba reasignacion exitosa a agente_2, se obtuvo exito={exito}, agente={agente_resultante}")
        return

    print("OK: agente reasignado correctamente de agente_1 a agente_2")


def test_reasignar_agente_ticket_inexistente():
    print("\n--- Prueba 11: reasignar_agente con ticket_id inexistente ---")
    try:
        ServicioTickets.reasignar_agente(
            ticket_id=999999,
            nuevo_agente_id=1,
        )
        print("FALLO: se esperaba TicketNoEncontradoError")
    except TicketNoEncontradoError:
        print("OK: fallo correctamente, ticket inexistente detectado")


def test_reasignar_agente_ticket_no_en_progreso():
    print("\n--- Prueba 12: reasignar_agente sobre ticket ABIERTO debe fallar ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    # ticket recien creado queda en ABIERTO, nunca paso por cambiar_estado

    try:
        ServicioTickets.reasignar_agente(
            ticket_id=ticket.id,
            nuevo_agente_id=agente_2.id,
        )
        print("FALLO: se esperaba TicketNoEnProgresoError")
    except TicketNoEnProgresoError:
        print("OK: fallo correctamente, ticket no estaba EN_PROGRESO")


def test_reasignar_agente_mismo_agente():
    print("\n--- Prueba 13: reasignar al mismo agente que ya tenia debe fallar ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente_1.id,
        agente_id=agente_1.id,
    )

    try:
        ServicioTickets.reasignar_agente(
            ticket_id=ticket.id,
            nuevo_agente_id=agente_1.id,
        )
        print("FALLO: se esperaba AgenteYaAsignadoError")
    except AgenteYaAsignadoError:
        print("OK: fallo correctamente, mismo agente detectado como conflicto")
def test_agregar_comentario_valido():
    print("\n--- Prueba 14: agregar comentario valido a un ticket ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    exito, comentario = ServicioTickets.agregar_comentario(
        ticket_id=ticket.id,
        autor_id=agente_1.id,
        texto="Estamos revisando tu caso, te contactaremos pronto.",
    )

    if not exito or comentario is None:
        print("FALLO: se esperaba que el comentario se creara exitosamente")
        return

    if comentario.ticket_id != ticket.id or comentario.autor_id != agente_1.id:
        print(f"FALLO: ticket_id o autor_id no coinciden, se obtuvo ticket_id={comentario.ticket_id}, autor_id={comentario.autor_id}")
        return

    print("OK: comentario agregado correctamente con los datos esperados")


def test_agregar_comentario_ticket_inexistente():
    print("\n--- Prueba 15: agregar_comentario con ticket_id inexistente ---")
    try:
        ServicioTickets.agregar_comentario(
            ticket_id=999999,
            autor_id=1,
            texto="comentario sobre ticket que no existe",
        )
        print("FALLO: se esperaba TicketNoEncontradoError")
    except TicketNoEncontradoError:
        print("OK: fallo correctamente, ticket inexistente detectado")


def test_agregar_comentario_texto_vacio():
    print("\n--- Prueba 16: agregar_comentario con texto vacio o solo espacios ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    _, ticket = ServicioTickets.crear_ticket(
        creador=usuario_normal,
        texto="no puedo entrar a mi correo",
    )

    try:
        ServicioTickets.agregar_comentario(
            ticket_id=ticket.id,
            autor_id=usuario_normal.id,
            texto="   ",
        )
        print("FALLO: se esperaba ComentarioVacioError")
    except ComentarioVacioError:
        print("OK: fallo correctamente, texto vacio/espacios detectado")
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        preparar_usuarios_de_prueba()
        test_ticket_normal_categoria_seguridad()
        test_ticket_vip_mismo_texto_sla_mas_corto()
        test_ticket_vip_categoria_baja_se_eleva_a_alta()
        test_listar_tickets_por_area_ordenados_por_prioridad()
        test_cambiar_estado_abierto_a_en_progreso()
        test_cambiar_estado_sin_agente_falla()
        test_cambiar_estado_agente_en_conflicto()
        test_cambiar_estado_transicion_invalida()
        test_cambiar_estado_ticket_inexistente()
        test_reasignar_agente_valido()
        test_reasignar_agente_ticket_inexistente()
        test_reasignar_agente_ticket_no_en_progreso()
        test_reasignar_agente_mismo_agente()
        test_agregar_comentario_valido()
        test_agregar_comentario_ticket_inexistente()
        test_agregar_comentario_texto_vacio()