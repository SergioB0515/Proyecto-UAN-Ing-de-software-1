"""
Pruebas de ServicioAutenticacion.iniciar_sesion()

Nota de migracion:
1. ServicioAutenticacion.iniciar_sesion ahora exige un tercer argumento
   obligatorio `ip` (bloqueo de IP tras 5 emails distintos fallidos en 1
   hora). Los scripts originales la llamaban con solo (email, contrasena) y
   ya no funcionaban contra el codigo actual de app/ (TypeError). Se agrego
   una IP fija de prueba (IP_PRUEBA) en todas las llamadas; como este archivo
   usa un solo email, no se acerca al umbral de bloqueo por IP.
2. La contraseña de prueba paso de "ClaveSegura123" a "ClaveSegura123!"
   porque validar_politica_contrasena ahora exige un simbolo (el registro
   fallaba con ValueError antes de llegar a nada de lo que prueba este archivo).

Estas pruebas son intencionalmente dependientes del orden de ejecucion (igual
que el script manual original): construyen sobre el contador de
intentos_fallidos que va dejando la prueba anterior. Pytest ejecuta los tests
de un archivo en el orden en que estan escritos, asi que el orden se preserva
sin necesidad de marcar nada extra.
"""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion, ResultadoLogin
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario


EMAIL_PRUEBA = "prueba_login@empresa.com"
EMAIL_ADMIN_PRUEBA = "prueba_login_admin@empresa.com"
CONTRASENA_CORRECTA = "ClaveSegura123!"
CONTRASENA_INCORRECTA = "ClaveEquivocada!"
IP_PRUEBA = "127.0.0.1"


@pytest.fixture(scope="module")
def admin_prueba():
    """Crea un admin directo por SQLAlchemy (sin pasar por registrar()) para poder
    llamar registrar() en las pruebas, que ahora requiere admin_id obligatorio."""
    admin_existente = Usuario.query.filter_by(email=EMAIL_ADMIN_PRUEBA).first()
    if admin_existente:
        db.session.delete(admin_existente)
        db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Login",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture(scope="module", autouse=True)
def usuario_prueba(admin_prueba):
    """Borra cualquier resto de corridas anteriores y crea un usuario fresco, sin bloqueos previos."""
    usuario_existente = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    if usuario_existente:
        db.session.delete(usuario_existente)
        db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Login Prueba",
        email=EMAIL_PRUEBA,
        contrasena=CONTRASENA_CORRECTA,
        rol=RolUsuario.FINAL,
        admin_id=admin_prueba.id,
    )


def test_login_exitoso():
    usuario, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_CORRECTA, IP_PRUEBA)

    assert estado == ResultadoLogin.EXITOSO, f"se esperaba EXITOSO, se obtuvo {estado}"
    assert usuario is not None, "se esperaba el objeto usuario, se obtuvo None"


def test_credenciales_invalidas():
    _, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_INCORRECTA, IP_PRUEBA)

    assert estado == ResultadoLogin.CREDENCIALES_INVALIDAS, f"se esperaba CREDENCIALES_INVALIDAS, se obtuvo {estado}"

    usuario_en_bd = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    assert usuario_en_bd.intentos_fallidos == 1, (
        f"se esperaba intentos_fallidos=1, se obtuvo {usuario_en_bd.intentos_fallidos}"
    )


def test_bloqueo_por_intentos_fallidos():
    # Ya llevamos 1 intento fallido de la prueba anterior, faltan 2 para llegar a 3
    estado = None
    for _ in range(2, 4):
        _, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_INCORRECTA, IP_PRUEBA)

    assert estado == ResultadoLogin.BLOQUEADO_AHORA, (
        f"el intento numero 3 debia devolver BLOQUEADO_AHORA, devolvio {estado}"
    )

    usuario_en_bd = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    assert usuario_en_bd.bloqueado_hasta is not None, (
        "bloqueado_hasta sigue en None despues del tercer intento fallido"
    )


def test_bloqueo_impide_login_aunque_contrasena_sea_correcta():
    usuario, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_CORRECTA, IP_PRUEBA)

    assert estado == ResultadoLogin.YA_BLOQUEADO, f"se esperaba YA_BLOQUEADO, se obtuvo {estado}"
    assert usuario is None, "no deberia devolver el usuario mientras esta bloqueado"


def test_bloqueo_expirado_no_deja_pasar_con_contrasena_incorrecta():
    usuario_en_bd = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    # Simula un bloqueo que ya venció (hace una hora)
    usuario_en_bd.bloqueado_hasta = datetime.now() - timedelta(hours=1)
    usuario_en_bd.intentos_fallidos = 3
    db.session.commit()

    _, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_INCORRECTA, IP_PRUEBA)
    assert estado == ResultadoLogin.CREDENCIALES_INVALIDAS, f"se esperaba CREDENCIALES_INVALIDAS, se obtuvo {estado}"

    # Y con la contraseña correcta sí debe entrar tras levantarse el bloqueo
    usuario, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_CORRECTA, IP_PRUEBA)
    assert estado == ResultadoLogin.EXITOSO and usuario is not None, (
        f"se esperaba EXITOSO con contraseña correcta, se obtuvo {estado}"
    )
