"""
Script de prueba manual para ServicioMetricas.obtener_metricas()

Como correrlo (desde la carpeta Proyecto, con el entorno virtual activado):
    python -m tests.test_metricas
"""

from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.metricas import ServicioMetricas
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad, EstadoTicket


EMAIL_NORMAL = "prueba_metricas_normal@empresa.com"
EMAIL_AGENTE = "prueba_metricas_agente@empresa.com"
EMAIL_ADMIN_PRUEBA = "prueba_metricas_admin@empresa.com"


def preparar_datos_de_prueba():
    for email in (EMAIL_NORMAL, EMAIL_AGENTE, EMAIL_ADMIN_PRUEBA):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Metricas",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Metricas Prueba",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Metricas Prueba",
        email=EMAIL_AGENTE,
        contrasena="ClaveSegura123",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )


def test_obtener_metricas():
    print("\n--- Prueba: obtener_metricas devuelve conteos correctos ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    ahora = datetime.now()

    # Ticket vencido dentro de los ultimos 30 dias, aun abierto
    ticket_vencido_reciente = Ticket(
        texto="ticket vencido reciente de prueba",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(days=10),
        fecha_limite=ahora - timedelta(days=5),
    )

    # Ticket vencido fuera del rango de 30 dias (no debe contar en esa metrica)
    ticket_vencido_viejo = Ticket(
        texto="ticket vencido viejo de prueba",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.BAJA,
        estado=EstadoTicket.CERRADO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(days=60),
        fecha_limite=ahora - timedelta(days=45),
    )

    db.session.add_all([ticket_vencido_reciente, ticket_vencido_viejo])
    db.session.commit()

    metricas = ServicioMetricas.obtener_metricas()

    campos_esperados = [
        "tickets_por_estado", "tickets_por_categoria", "tickets_por_prioridad",
        "tickets_vencidos_actualmente", "tickets_proximos_a_vencer_actualmente",
        "tickets_vencidos_ultimos_30_dias", "cantidad_agentes",
    ]
    for campo in campos_esperados:
        if campo not in metricas:
            print(f"FALLO: falta el campo '{campo}' en el resultado")
            return

    if metricas["tickets_vencidos_ultimos_30_dias"] < 1:
        print(f"FALLO: se esperaba al menos 1 ticket vencido en los ultimos 30 dias, se obtuvo {metricas['tickets_vencidos_ultimos_30_dias']}")
        return

    if metricas["cantidad_agentes"] < 1:
        print(f"FALLO: se esperaba al menos 1 agente, se obtuvo {metricas['cantidad_agentes']}")
        return

    print(f"OK: metricas obtenidas correctamente")
    print(f"  tickets_por_estado={metricas['tickets_por_estado']}")
    print(f"  tickets_por_categoria={metricas['tickets_por_categoria']}")
    print(f"  tickets_por_prioridad={metricas['tickets_por_prioridad']}")
    print(f"  tickets_vencidos_actualmente={metricas['tickets_vencidos_actualmente']}")
    print(f"  tickets_proximos_a_vencer_actualmente={metricas['tickets_proximos_a_vencer_actualmente']}")
    print(f"  tickets_vencidos_ultimos_30_dias={metricas['tickets_vencidos_ultimos_30_dias']}")
    print(f"  cantidad_agentes={metricas['cantidad_agentes']}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        preparar_datos_de_prueba()
        test_obtener_metricas()