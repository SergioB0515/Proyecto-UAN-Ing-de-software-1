"""
Pruebas de ServicioNotificaciones

Que verifica:
1. crear: caso valido (guarda con leida=False por defecto).
2. crear: poda automatica -- al superar LIMITE_POR_USUARIO (15), se borra
   la mas vieja y se conserva exactamente 15, con la mas reciente presente
   y la mas antigua ausente. Este es el test mas importante del archivo:
   ejercita crear() en un loop real, tal como se usaria en produccion, no
   con datos insertados a mano saltandose la logica de poda.
3. crear: la poda es por usuario -- notificaciones de otro usuario no
   cuentan para el limite de este usuario ni se ven afectadas.
4. listar_para_usuario: orden mas reciente primero, solo las de ese usuario.
5. contar_no_leidas: cuenta solo las no leidas, solo las de ese usuario.
6. marcar_leida: caso valido (devuelve la notificacion, leida pasa a True).
7. marcar_leida: notificacion inexistente -> no truena, devuelve None.
8. marcar_leida: notificacion de otro usuario -> no la toca, devuelve None
   (chequeo de propiedad).
"""
import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.notificaciones import ServicioNotificaciones
from app.models.usuario import Usuario
from app.models.notificacion import Notificacion
from app.models.enum import RolUsuario, NivelUsuario


EMAIL_ADMIN = "prueba_notificaciones_admin@empresa.com"
EMAIL_USUARIO_A = "prueba_notificaciones_a@empresa.com"
EMAIL_USUARIO_B = "prueba_notificaciones_b@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_USUARIO_A, EMAIL_USUARIO_B):
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
        nombre="Usuario Notificaciones A",
        email=EMAIL_USUARIO_A,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario Notificaciones B",
        email=EMAIL_USUARIO_B,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )


def _limpiar_notificaciones(usuario_id):
    """Helper local: borra cualquier notificacion previa de ese usuario,
    para que cada test que dependa de un conteo exacto empiece en cero."""
    db.session.query(Notificacion).filter(Notificacion.usuario_id == usuario_id).delete()
    db.session.commit()


# ---------------------------------------------------------------------------
# crear
# ---------------------------------------------------------------------------

def test_crear_valido():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(
        usuario_id=usuario_a.id, mensaje="Notificacion de prueba",
    )

    notificaciones = ServicioNotificaciones.listar_para_usuario(usuario_a.id)
    assert len(notificaciones) == 1, (
        f"se esperaba 1 notificacion, se obtuvieron {len(notificaciones)}"
    )
    assert notificaciones[0].leida is False, (
        "una notificacion recien creada debe empezar como no leida"
    )
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
        f"se esperaban exactamente {ServicioNotificaciones.LIMITE_POR_USUARIO} "
        f"notificaciones tras la poda, se obtuvieron {len(notificaciones)}"
    )

    mensajes = {n.mensaje for n in notificaciones}
    assert "Mensaje 0" not in mensajes, (
        "la notificacion mas antigua (Mensaje 0) deberia haber sido borrada por la poda"
    )
    assert "Mensaje 15" in mensajes, (
        "la notificacion mas reciente (Mensaje 15) deberia seguir presente"
    )


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
        "la poda del usuario A no deberia afectar en absoluto las notificaciones del usuario B, "
        f"se obtuvieron {len(notificaciones_b)}"
    )


# ---------------------------------------------------------------------------
# listar_para_usuario
# ---------------------------------------------------------------------------

def test_listar_para_usuario_orden_mas_reciente_primero():
    usuario_a = Usuario.query.filter_by(email=EMAIL_USUARIO_A).first()
    _limpiar_notificaciones(usuario_a.id)

    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Primera")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Segunda")
    ServicioNotificaciones.crear(usuario_id=usuario_a.id, mensaje="Tercera")

    notificaciones = ServicioNotificaciones.listar_para_usuario(usuario_a.id)

    assert notificaciones[0].mensaje == "Tercera", (
        f"se esperaba que la mas reciente fuera primero, se obtuvo '{notificaciones[0].mensaje}'"
    )
    assert notificaciones[-1].mensaje == "Primera", (
        f"se esperaba que la mas antigua fuera ultima, se obtuvo '{notificaciones[-1].mensaje}'"
    )


# ---------------------------------------------------------------------------
# contar_no_leidas
# ---------------------------------------------------------------------------

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
    assert contador_b == 0, (
        f"las notificaciones del usuario A no deberian contar para B, se obtuvo {contador_b}"
    )


# ---------------------------------------------------------------------------
# marcar_leida
# ---------------------------------------------------------------------------

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

    assert resultado is None, (
        "usuario B no deberia poder marcar como leida una notificacion que pertenece a usuario A"
    )

    notificacion_sin_tocar = db.session.get(Notificacion, notificacion_de_a.id)
    assert notificacion_sin_tocar.leida is False, (
        "el intento de usuario B no debio modificar la notificacion real de A"
    )


# ---------------------------------------------------------------------------
# marcar_todas_leidas
# ---------------------------------------------------------------------------

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
    assert ServicioNotificaciones.contar_no_leidas(usuario_a.id) == 0, (
        "tras marcar todas, el usuario A no debe tener notificaciones sin leer"
    )
    assert ServicioNotificaciones.contar_no_leidas(usuario_b.id) == 1, (
        "marcar todas las de A no debe tocar las de B"
    )