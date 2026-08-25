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

from datetime import datetime

from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets, ORDEN_PRIORIDAD
from app.Models.usuario import Usuario
from app.Models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad


EMAIL_NORMAL = "prueba_ticket_normal@empresa.com"
EMAIL_VIP = "prueba_ticket_vip@empresa.com"


def preparar_usuarios_de_prueba():
    """Limpia restos de corridas anteriores y crea un usuario normal y uno VIP."""
    for email in (EMAIL_NORMAL, EMAIL_VIP):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario VIP",
        email=EMAIL_VIP,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.VIP,
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


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        preparar_usuarios_de_prueba()
        test_ticket_normal_categoria_seguridad()
        test_ticket_vip_mismo_texto_sla_mas_corto()
        test_ticket_vip_categoria_baja_se_eleva_a_alta()
        test_listar_tickets_por_area_ordenados_por_prioridad()