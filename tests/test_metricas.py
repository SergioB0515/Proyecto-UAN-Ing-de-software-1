"""
Script de prueba manual para la logica de tickets_vencidos_ultimos_30_dias
en ServicioMetricas.obtener_metricas()

Cubre la semantica definida: union de
  (a) cerrados fuera de plazo (fecha_cierre > fecha_limite)
  (b) aun abiertos y con fecha_limite ya vencida
ambos con fecha_limite dentro de los ultimos 30 dias.

Usa medicion por delta (metrica antes vs. despues de insertar los tickets
de prueba) para que la asercion sea exacta sin importar cuantos tickets
de corridas anteriores ya existan en la base de datos.

Como correrlo (desde la carpeta Proyecto, con el entorno virtual activado):
    python -m tests.test_metricas_vencidos_30_dias
"""

from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.metricas import ServicioMetricas
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad, EstadoTicket


EMAIL_ADMIN_PRUEBA = "prueba_v30d_admin@empresa.com"
EMAIL_NORMAL = "prueba_v30d_normal@empresa.com"

MARCADOR_TEXTO = "[TEST_V30D]"


def limpiar_datos_de_prueba():
    """Elimina tickets y usuarios de corridas anteriores de este test especifico."""
    tickets_previos = Ticket.query.filter(Ticket.texto.like(f"{MARCADOR_TEXTO}%")).all()
    for t in tickets_previos:
        db.session.delete(t)
    db.session.commit()

    for email in (EMAIL_NORMAL, EMAIL_ADMIN_PRUEBA):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()


def preparar_datos_de_prueba():
    limpiar_datos_de_prueba()

    admin_prueba = Usuario(
        nombre="Admin Prueba V30D",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario V30D Prueba",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )


def test_union_cerrados_tarde_y_vencidos_sin_cerrar():
    print("\n--- Prueba: tickets_vencidos_ultimos_30_dias (union cerrados tarde + abiertos vencidos) ---")
    usuario_normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    ahora = datetime.now()

    # Medicion base ANTES de insertar los tickets de prueba
    metricas_antes = ServicioMetricas.obtener_metricas()
    valor_antes = metricas_antes["tickets_vencidos_ultimos_30_dias"]

    casos = []

    # (a) Cerrado A TIEMPO, dentro de los ultimos 30 dias -> NO debe contar
    casos.append(Ticket(
        texto=f"{MARCADOR_TEXTO} cerrado a tiempo",
        categoria=Categoria.SOFTWARE, prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.CERRADO, creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(days=10),
        fecha_limite=ahora - timedelta(days=5),
        fecha_cierre=ahora - timedelta(days=6),  # cerro ANTES del limite
    ))

    # (b) Cerrado TARDE, dentro de los ultimos 30 dias -> SI debe contar (condicion a)
    casos.append(Ticket(
        texto=f"{MARCADOR_TEXTO} cerrado tarde",
        categoria=Categoria.SOFTWARE, prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.CERRADO, creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(days=10),
        fecha_limite=ahora - timedelta(days=5),
        fecha_cierre=ahora - timedelta(days=2),  # cerro DESPUES del limite
    ))

    # (c) Vencido y AUN ABIERTO, dentro de los ultimos 30 dias -> SI debe contar (condicion b)
    casos.append(Ticket(
        texto=f"{MARCADOR_TEXTO} vencido sin cerrar",
        categoria=Categoria.SOFTWARE, prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.EN_PROGRESO, creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(days=10),
        fecha_limite=ahora - timedelta(days=3),
        fecha_cierre=None,
    ))

    # (d) Vigente, fecha_limite en el futuro -> NO debe contar
    casos.append(Ticket(
        texto=f"{MARCADOR_TEXTO} vigente no vencido",
        categoria=Categoria.SOFTWARE, prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO, creador_id=usuario_normal.id,
        fecha_creacion=ahora,
        fecha_limite=ahora + timedelta(days=5),
        fecha_cierre=None,
    ))

    # (e) Vencido pero FUERA del rango de 30 dias -> NO debe contar
    casos.append(Ticket(
        texto=f"{MARCADOR_TEXTO} vencido fuera de rango",
        categoria=Categoria.SOFTWARE, prioridad=Prioridad.BAJA,
        estado=EstadoTicket.ABIERTO, creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(days=60),
        fecha_limite=ahora - timedelta(days=45),
        fecha_cierre=None,
    ))

    db.session.add_all(casos)
    db.session.commit()

    metricas_despues = ServicioMetricas.obtener_metricas()
    valor_despues = metricas_despues["tickets_vencidos_ultimos_30_dias"]

    delta = valor_despues - valor_antes
    esperado = 2  # solo (b) y (c) deben contar

    if delta != esperado:
        print(f"FALLO: se esperaba un delta de {esperado} tickets nuevos contados, "
              f"se obtuvo {delta} (antes={valor_antes}, despues={valor_despues})")
        return

    print(f"OK: delta correcto = {delta} "
          f"(cerrado a tiempo excluido, cerrado tarde incluido, "
          f"vencido sin cerrar incluido, vigente excluido, fuera de rango excluido)")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        preparar_datos_de_prueba()
        test_union_cerrados_tarde_y_vencidos_sin_cerrar()
        limpiar_datos_de_prueba()