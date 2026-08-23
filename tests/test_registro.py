"""
Script de prueba manual para ServicioAutenticacion.registrar()

Como correrlo (desde la carpeta Proyecto, con el entorno virtual activado):
    python -m tests.test_registro

Que verifica:
1. Que un usuario nuevo se registra correctamente.
2. Que la contraseña se guarda como hash, NUNCA en texto plano.
3. Que intentar registrar el mismo email dos veces falla la segunda vez.
"""

from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.Models.usuario import Usuario
from app.Models.enum import RolUsuario, NivelUsuario


def limpiar_usuario_de_prueba(email):
    """Borra el usuario de prueba si ya existe, para poder correr el script varias veces sin chocar."""
    usuario_existente = Usuario.query.filter_by(email=email).first()
    if usuario_existente:
        db.session.delete(usuario_existente)
        db.session.commit()


def test_registro_exitoso():
    print("\n--- Prueba 1: registro exitoso ---")
    email_prueba = "prueba_registro@empresa.com"
    limpiar_usuario_de_prueba(email_prueba)

    resultado = ServicioAutenticacion.registrar(
        nombre="Usuario de Prueba",
        email=email_prueba,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
    )

    if resultado is not True:
        print(f"FALLO: se esperaba True, se obtuvo {resultado}")
        return

    usuario_guardado = Usuario.query.filter_by(email=email_prueba).first()
    if usuario_guardado is None:
        print("FALLO: el usuario no quedó guardado en la base de datos")
        return

    # Verificación crítica: la contraseña NUNCA debe quedar en texto plano
    if usuario_guardado.contrasena_hash == "ClaveSegura123":
        print("FALLO GRAVE: la contraseña se guardó en texto plano")
        return

    if not usuario_guardado.contrasena_hash.startswith("$2b$"):
        print(f"FALLO: el hash no tiene el formato esperado de bcrypt: {usuario_guardado.contrasena_hash}")
        return

    print("OK: usuario registrado y contraseña almacenada como hash bcrypt")


def test_email_duplicado():
    print("\n--- Prueba 2: email duplicado debe rechazarse ---")
    email_prueba = "duplicado@empresa.com"
    limpiar_usuario_de_prueba(email_prueba)

    primer_intento = ServicioAutenticacion.registrar(
        nombre="Primer Usuario",
        email=email_prueba,
        contrasena="Clave123",
        rol=RolUsuario.FINAL,
    )
    segundo_intento = ServicioAutenticacion.registrar(
        nombre="Segundo Usuario (mismo email)",
        email=email_prueba,
        contrasena="OtraClave456",
        rol=RolUsuario.FINAL,
    )

    if primer_intento is not True:
        print(f"FALLO: el primer registro debía ser exitoso (True), fue {primer_intento}")
        return

    if segundo_intento is not False:
        print(f"FALLO: el segundo registro debía ser rechazado (False), fue {segundo_intento}")
        return

    print("OK: el segundo registro con email duplicado fue rechazado correctamente")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        test_registro_exitoso()
        test_email_duplicado()