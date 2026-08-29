from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario

EMAIL_ADMIN = "admin@empresa.com"

def crear_admin_inicial():
    admin_existente = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    if admin_existente:
        print(f"Ya existe un admin con el email {EMAIL_ADMIN}, no se crea de nuevo.")
        return admin_existente

    hash_contrasena = ServicioAutenticacion._generar_hash("CAMBIAR_ESTA_CLAVE")

    admin = Usuario(
        nombre="Administrador",
        email=EMAIL_ADMIN,
        contrasena_hash=hash_contrasena,
        rol=RolUsuario.ADMIN, 
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()
    print(f"Admin inicial creado con id={admin.id}, email={admin.email}")
    return admin

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        crear_admin_inicial()
