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
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario


EMAIL_ADMIN_PRUEBA = "prueba_registro_admin@empresa.com"


def limpiar_usuario_de_prueba(email):
    """Borra el usuario de prueba si ya existe, para poder correr el script varias veces sin chocar."""
    usuario_existente = Usuario.query.filter_by(email=email).first()
    if usuario_existente:
        db.session.delete(usuario_existente)
        db.session.commit()


def preparar_admin_de_prueba():
    """Crea un admin directo por SQLAlchemy (sin pasar por registrar()) para poder
    llamar registrar() en las pruebas, que ahora requiere admin_id obligatorio."""
    limpiar_usuario_de_prueba(EMAIL_ADMIN_PRUEBA)

    admin_prueba = Usuario(
        nombre="Admin Prueba Registro",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()
    return admin_prueba


def test_registro_exitoso(admin_id):
    print("\n--- Prueba 1: registro exitoso ---")
    email_prueba = "prueba_registro@empresa.com"
    limpiar_usuario_de_prueba(email_prueba)

    resultado = ServicioAutenticacion.registrar(
        nombre="Usuario de Prueba",
        email=email_prueba,
        contrasena="ClaveSegura123",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_id,
    )

    if resultado is None:
        print(f"FALLO: se esperaba el usuario creado, se obtuvo {resultado}")
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


def test_email_duplicado(admin_id):
    print("\n--- Prueba 2: email duplicado debe rechazarse ---")
    email_prueba = "duplicado@empresa.com"
    limpiar_usuario_de_prueba(email_prueba)

    primer_intento = ServicioAutenticacion.registrar(
        nombre="Primer Usuario",
        email=email_prueba,
        contrasena="Clave123",
        rol=RolUsuario.FINAL,
        admin_id=admin_id,
    )
    segundo_intento = ServicioAutenticacion.registrar(
        nombre="Segundo Usuario (mismo email)",
        email=email_prueba,
        contrasena="OtraClave456",
        rol=RolUsuario.FINAL,
        admin_id=admin_id,
    )

    if primer_intento is None:
        print(f"FALLO: el primer registro debía crear el usuario, fue {primer_intento}")
        return

    if segundo_intento is not None:
        print(f"FALLO: el segundo registro debía ser rechazado (None), fue {segundo_intento}")
        return

    print("OK: el segundo registro con email duplicado fue rechazado correctamente")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        admin_prueba = preparar_admin_de_prueba()
        test_registro_exitoso(admin_id=admin_prueba.id)
        test_email_duplicado(admin_id=admin_prueba.id)