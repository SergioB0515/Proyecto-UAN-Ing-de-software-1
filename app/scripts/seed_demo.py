"""
Todos los usuarios de demo comparten la contraseña 'ClaveSegura123!'.
"""
from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket

EMAIL_ADMIN_DEMO = "admin.demo@empresa.com"
CONTRASENA_DEMO = "ClaveSegura123!"


def _registrar_si_no_existe(nombre, email, rol, admin_id, area_soporte=None, nivel=NivelUsuario.NORMAL):
    existente = Usuario.query.filter_by(email=email).first()
    if existente:
        return existente
    return ServicioAutenticacion.registrar(
        nombre=nombre, email=email, contrasena=CONTRASENA_DEMO,
        rol=rol, admin_id=admin_id, area_soporte=area_soporte, nivel=nivel,
    )


def sembrar():
    if Usuario.query.filter_by(email=EMAIL_ADMIN_DEMO).first():
        print(f"Ya existen datos de demo ({EMAIL_ADMIN_DEMO} ya existe). No se siembra de nuevo.")
        return

    admin = Usuario(
        nombre="Admin Demo",
        email=EMAIL_ADMIN_DEMO,
        contrasena_hash=ServicioAutenticacion._generar_hash(CONTRASENA_DEMO),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()
    print(f"Admin demo creado: {admin.email}")


    normal_1 = _registrar_si_no_existe("Carlos Ramirez", "carlos.ramirez@empresa.com", RolUsuario.FINAL, admin.id)
    normal_2 = _registrar_si_no_existe("Laura Gomez", "laura.gomez@empresa.com", RolUsuario.FINAL, admin.id)
    normal_3 = _registrar_si_no_existe("Julian Torres", "julian.torres@empresa.com", RolUsuario.FINAL, admin.id)
    vip_1 = _registrar_si_no_existe("Marcela Duque", "marcela.duque@empresa.com", RolUsuario.FINAL, admin.id, nivel=NivelUsuario.VIP)
    print("Usuarios finales creados (3 normales, 1 VIP)")

    agente_permisos_1 = _registrar_si_no_existe("Andres Pena", "andres.pena@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.PERMISOS)
    agente_permisos_2 = _registrar_si_no_existe("Diana Rios", "diana.rios@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.PERMISOS)
    agente_seguridad = _registrar_si_no_existe("Felipe Castro", "felipe.castro@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.SEGURIDAD)
    agente_redes = _registrar_si_no_existe("Sandra Vega", "sandra.vega@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.REDES)
    agente_infra = _registrar_si_no_existe("Oscar Mendez", "oscar.mendez@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.INFRAESTRUCTURA)
    _registrar_si_no_existe("Paula Nino", "paula.nino@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.CUENTAS_CONTRASENAS)
    _registrar_si_no_existe("Ricardo Leon", "ricardo.leon@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.SOFTWARE)
    _registrar_si_no_existe("Ivan Salazar", "ivan.salazar@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.OTROS)
    print("Agentes creados: 2 en Permisos, 1 por cada otra area")


    t1 = ServicioTickets.crear_ticket(creador=normal_1, texto="no tengo acceso a la carpeta compartida de ventas")           # PERMISOS
    t2 = ServicioTickets.crear_ticket(creador=normal_2, texto="alguien entró a mi cuenta sin permiso, no fui yo")            # SEGURIDAD
    t3 = ServicioTickets.crear_ticket(creador=normal_3, texto="no hay wifi en toda la oficina")                              # REDES
    t4 = ServicioTickets.crear_ticket(creador=vip_1, texto="mi computador no enciende desde esta mañana")                    # INFRAESTRUCTURA, VIP -> ALTA
    t5 = ServicioTickets.crear_ticket(creador=normal_1, texto="olvidé mi contraseña y necesito cambiarla")                   # CUENTAS_CONTRASENAS
    t6 = ServicioTickets.crear_ticket(creador=normal_2, texto="el programa de facturación se cierra solo")                   # SOFTWARE
    t7 = ServicioTickets.crear_ticket(creador=normal_3, texto="quisiera saber si puedo pedir vacaciones la próxima semana")  # OTROS
    t8 = ServicioTickets.crear_ticket(creador=vip_1, texto="no puedo abrir la carpeta de nomina")                            # PERMISOS, VIP -> ALTA
    print(f"8 tickets creados (ids {t1.id}-{t8.id}), uno por categoria mas un segundo en Permisos")


    ServicioTickets.cambiar_estado(ticket_id=t1.id, nuevo_estado=EstadoTicket.EN_PROGRESO, actor_id=agente_permisos_1.id, agente_id=agente_permisos_1.id)
    ServicioTickets.cambiar_estado(ticket_id=t2.id, nuevo_estado=EstadoTicket.EN_PROGRESO, actor_id=agente_seguridad.id, agente_id=agente_seguridad.id)
    ServicioTickets.cambiar_estado(ticket_id=t2.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=agente_seguridad.id)
    ServicioTickets.cambiar_estado(ticket_id=t8.id, nuevo_estado=EstadoTicket.EN_PROGRESO, actor_id=agente_permisos_1.id, agente_id=agente_permisos_1.id)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        sembrar()
