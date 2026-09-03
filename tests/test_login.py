from datetime import datetime, timedelta

from tests import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion, ResultadoLogin
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario


EMAIL_PRUEBA = "prueba_login@empresa.com"
EMAIL_ADMIN_PRUEBA = "prueba_login_admin@empresa.com"
CONTRASENA_CORRECTA = "ClaveSegura123"
CONTRASENA_INCORRECTA = "ClaveEquivocada"


def preparar_admin_de_prueba():
    """Crea un admin directo por SQLAlchemy (sin pasar por registrar()) para poder
    llamar registrar() en las pruebas, que ahora requiere admin_id obligatorio."""
    admin_existente = Usuario.query.filter_by(email=EMAIL_ADMIN_PRUEBA).first()
    if admin_existente:
        db.session.delete(admin_existente)
        db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Login",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()
    return admin_prueba


def preparar_usuario_de_prueba(admin_id):
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
        admin_id=admin_id,
    )


def test_login_exitoso():
    print("\n--- Prueba 1: login con credenciales correctas ---")
    usuario, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_CORRECTA)

    if estado != ResultadoLogin.EXITOSO:
        print(f"FALLO: se esperaba EXITOSO, se obtuvo {estado}")
        return
    if usuario is None:
        print("FALLO: se esperaba el objeto usuario, se obtuvo None")
        return

    print("OK: login exitoso con credenciales correctas")


def test_credenciales_invalidas():
    print("\n--- Prueba 2: contraseña incorrecta (un intento) ---")
    _, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_INCORRECTA)

    if estado != ResultadoLogin.CREDENCIALES_INVALIDAS:
        print(f"FALLO: se esperaba CREDENCIALES_INVALIDAS, se obtuvo {estado}")
        return

    usuario_en_bd = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    if usuario_en_bd.intentos_fallidos != 1:
        print(f"FALLO: se esperaba intentos_fallidos=1, se obtuvo {usuario_en_bd.intentos_fallidos}")
        return

    print("OK: contraseña incorrecta rechazada y contador de intentos actualizado en la base de datos")


def test_bloqueo_por_intentos_fallidos():
    print("\n--- Prueba 3: 5 intentos fallidos seguidos deben bloquear la cuenta ---")
    # Ya llevamos 1 intento fallido de la prueba anterior, faltan 4 para llegar a 5
    for numero_intento in range(2, 6):
        _, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_INCORRECTA)
        print(f"  Intento {numero_intento}: {estado}")

    if estado != ResultadoLogin.BLOQUEADO_AHORA:
        print(f"FALLO: el intento numero 5 debia devolver BLOQUEADO_AHORA, devolvio {estado}")
        return

    usuario_en_bd = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    if usuario_en_bd.bloqueado_hasta is None:
        print("FALLO: bloqueado_hasta sigue en None despues del quinto intento fallido")
        return

    print("OK: la cuenta quedo bloqueada tras 5 intentos fallidos seguidos")


def test_bloqueo_impide_login_aunque_contrasena_sea_correcta():
    print("\n--- Prueba 4: cuenta ya bloqueada debe rechazar incluso la contraseña correcta ---")
    usuario, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_CORRECTA)

    if estado != ResultadoLogin.YA_BLOQUEADO:
        print(f"FALLO: se esperaba YA_BLOQUEADO, se obtuvo {estado}")
        return
    if usuario is not None:
        print("FALLO: no deberia devolver el usuario mientras esta bloqueado")
        return

    print("OK: la cuenta bloqueada rechaza el login incluso con la contraseña correcta")


def test_bloqueo_expirado_no_deja_pasar_con_contrasena_incorrecta():
    print("\n--- Prueba 5: bloqueo ya expirado no debe autenticar con contraseña incorrecta ---")
    usuario_en_bd = Usuario.query.filter_by(email=EMAIL_PRUEBA).first()
    # Simula un bloqueo que ya venció (hace una hora)
    usuario_en_bd.bloqueado_hasta = datetime.now() - timedelta(hours=1)
    usuario_en_bd.intentos_fallidos = 5
    db.session.commit()

    _, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_INCORRECTA)
    if estado != ResultadoLogin.CREDENCIALES_INVALIDAS:
        print(f"FALLO: se esperaba CREDENCIALES_INVALIDAS, se obtuvo {estado}")
        return

    # Y con la contraseña correcta sí debe entrar tras levantarse el bloqueo
    usuario, estado = ServicioAutenticacion.iniciar_sesion(EMAIL_PRUEBA, CONTRASENA_CORRECTA)
    if estado != ResultadoLogin.EXITOSO or usuario is None:
        print(f"FALLO: se esperaba EXITOSO con contraseña correcta, se obtuvo {estado}")
        return

    print("OK: el bloqueo expirado se levanta pero sigue validando la contraseña")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        admin_prueba = preparar_admin_de_prueba()
        preparar_usuario_de_prueba(admin_id=admin_prueba.id)
        test_login_exitoso()
        test_credenciales_invalidas()
        test_bloqueo_por_intentos_fallidos()
        test_bloqueo_impide_login_aunque_contrasena_sea_correcta()
        test_bloqueo_expirado_no_deja_pasar_con_contrasena_incorrecta()