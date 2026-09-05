"""
Pruebas de ServicioAutenticacion.registrar()

Que verifica:
1. Que un usuario nuevo se registra correctamente.
2. Que la contraseña se guarda como hash, NUNCA en texto plano.
3. Que intentar registrar el mismo email dos veces falla la segunda vez.

Nota de migracion: las contraseñas de prueba se cambiaron de "ClaveSegura123"
a "ClaveSegura123!" (y similares) porque validar_politica_contrasena ahora
exige al menos un simbolo; con las contraseñas originales, registrar()
lanzaba ValueError antes de llegar a la logica que estas pruebas verifican.
"""
import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario


EMAIL_ADMIN_PRUEBA = "prueba_registro_admin@empresa.com"


def limpiar_usuario_de_prueba(email):
    """Borra el usuario de prueba si ya existe, para poder correr la suite varias veces sin chocar."""
    usuario_existente = Usuario.query.filter_by(email=email).first()
    if usuario_existente:
        db.session.delete(usuario_existente)
        db.session.commit()


@pytest.fixture(scope="module")
def admin_prueba():
    """Crea un admin directo por SQLAlchemy (sin pasar por registrar()) para poder
    llamar registrar() en las pruebas, que ahora requiere admin_id obligatorio."""
    limpiar_usuario_de_prueba(EMAIL_ADMIN_PRUEBA)

    admin = Usuario(
        nombre="Admin Prueba Registro",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()
    return admin


def test_registro_exitoso(admin_prueba):
    email_prueba = "prueba_registro@empresa.com"
    limpiar_usuario_de_prueba(email_prueba)

    resultado = ServicioAutenticacion.registrar(
        nombre="Usuario de Prueba",
        email=email_prueba,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )

    assert resultado is not None, f"se esperaba el usuario creado, se obtuvo {resultado}"

    usuario_guardado = Usuario.query.filter_by(email=email_prueba).first()
    assert usuario_guardado is not None, "el usuario no quedó guardado en la base de datos"

    # Verificación crítica: la contraseña NUNCA debe quedar en texto plano
    assert usuario_guardado.contrasena_hash != "ClaveSegura123!", (
        "FALLO GRAVE: la contraseña se guardó en texto plano"
    )

    assert usuario_guardado.contrasena_hash.startswith("$2b$"), (
        f"el hash no tiene el formato esperado de bcrypt: {usuario_guardado.contrasena_hash}"
    )


def test_email_duplicado(admin_prueba):
    email_prueba = "duplicado@empresa.com"
    limpiar_usuario_de_prueba(email_prueba)

    primer_intento = ServicioAutenticacion.registrar(
        nombre="Primer Usuario",
        email=email_prueba,
        contrasena="Clave123!",
        rol=RolUsuario.FINAL,
        admin_id=admin_prueba.id,
    )
    segundo_intento = ServicioAutenticacion.registrar(
        nombre="Segundo Usuario (mismo email)",
        email=email_prueba,
        contrasena="OtraClave456!",
        rol=RolUsuario.FINAL,
        admin_id=admin_prueba.id,
    )

    assert primer_intento is not None, f"el primer registro debía crear el usuario, fue {primer_intento}"
    assert segundo_intento is None, f"el segundo registro debía ser rechazado (None), fue {segundo_intento}"
