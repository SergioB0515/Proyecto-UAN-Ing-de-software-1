"""
Todos los usuarios de demo comparten la contraseña 'ClaveSegura123!'.
"""
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, Prioridad

EMAIL_ADMIN_DEMO = "admin.demo@empresa.com"
CONTRASENA_DEMO = "ClaveSegura123!"

# Horas de SLA para nivel NORMAL, segun prioridad (ver documentacion/03_logica.md)
HORAS_SLA_NORMAL = {
    Prioridad.ALTA: 4,
    Prioridad.MEDIA: 24,
    Prioridad.BAJA: 72,
}


def _registrar_si_no_existe(nombre, email, rol, admin_id, area_soporte=None, nivel=NivelUsuario.NORMAL):
    existente = Usuario.query.filter_by(email=email).first()
    if existente:
        return existente
    return ServicioAutenticacion.registrar(
        nombre=nombre, email=email, contrasena=CONTRASENA_DEMO,
        rol=rol, admin_id=admin_id, area_soporte=area_soporte, nivel=nivel,
    )


def _crear_ticket_historico(creador_id, agente_id, categoria, prioridad, texto,
                             dias_desde_asignacion, horas_hasta_cierre):
    """
    Crea un ticket ya CERRADO con fechas fijadas directamente -- sin pasar
    por ServicioTickets/GestorSLA, que siempre usan datetime.now() y no
    permiten backdatear. Necesario para poblar datos historicos de demo
    con variacion real de tiempo de resolucion y cumplimiento de SLA
    (mismo patron que tests/test_metricas_agente.py::_crear_ticket_cerrado).

    dias_desde_asignacion: hace cuantos dias se asigno el ticket al agente.
    horas_hasta_cierre: cuantas horas despues de la asignacion se cerro
        (comparado contra horas_sla para determinar si cumplio o no).
    """
    ahora = datetime.now()
    fecha_asignacion = ahora - timedelta(days=dias_desde_asignacion)
    fecha_cierre = fecha_asignacion + timedelta(hours=horas_hasta_cierre)
    horas_sla = HORAS_SLA_NORMAL[prioridad]
    fecha_limite = fecha_asignacion + timedelta(hours=horas_sla)

    ticket = Ticket(
        texto=texto,
        categoria=categoria,
        prioridad=prioridad,
        estado=EstadoTicket.CERRADO,
        creador_id=creador_id,
        agente_id=agente_id,
        fecha_creacion=fecha_asignacion - timedelta(minutes=20),
        fecha_asignacion=fecha_asignacion,
        fecha_limite=fecha_limite,
        fecha_cierre=fecha_cierre,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket



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
    agente_cuentas = _registrar_si_no_existe("Paula Nino", "paula.nino@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.CUENTAS_CONTRASENAS)
    agente_software = _registrar_si_no_existe("Ricardo Leon", "ricardo.leon@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.SOFTWARE)
    agente_otros = _registrar_si_no_existe("Ivan Salazar", "ivan.salazar@empresa.com", RolUsuario.AGENTE, admin.id, area_soporte=Categoria.OTROS)
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


    # --- Historico de tickets cerrados (ultimos 30 dias) para el panel de
    # metricas por agente (v2.2) -- variacion deliberada de cumplimiento_sla
    # y tiempo_promedio_resolucion_horas para que el grafico y las tablas
    # muestren diferencias reales entre agentes, no una linea plana.

    creadores = [normal_1.id, normal_2.id, normal_3.id]

    # Andres (Permisos) -- buen desempeño: 3/4 a tiempo
    _crear_ticket_historico(creadores[0], agente_permisos_1.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "no puedo abrir un archivo compartido", dias_desde_asignacion=25, horas_hasta_cierre=4)
    _crear_ticket_historico(creadores[1], agente_permisos_1.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "necesito acceso a la unidad de red", dias_desde_asignacion=18, horas_hasta_cierre=10)
    _crear_ticket_historico(creadores[2], agente_permisos_1.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "no me deja entrar al sistema de nomina", dias_desde_asignacion=10, horas_hasta_cierre=2)
    _crear_ticket_historico(creadores[0], agente_permisos_1.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "acceso denegado a la carpeta de contratos", dias_desde_asignacion=5, horas_hasta_cierre=90)

    # Diana (Permisos, mismo area que Andres) -- desempeño bajo: 1/3 a tiempo
    _crear_ticket_historico(creadores[1], agente_permisos_2.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "no puedo ver la carpeta del proyecto", dias_desde_asignacion=20, horas_hasta_cierre=80)
    _crear_ticket_historico(creadores[2], agente_permisos_2.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "acceso denegado a reportes financieros", dias_desde_asignacion=12, horas_hasta_cierre=90)
    _crear_ticket_historico(creadores[0], agente_permisos_2.id, Categoria.PERMISOS, Prioridad.BAJA,
                             "no tengo permisos en el servidor", dias_desde_asignacion=6, horas_hasta_cierre=20)

    # Felipe (Seguridad) -- excelente: 3/3 a tiempo, rapido
    _crear_ticket_historico(creadores[0], agente_seguridad.id, Categoria.SEGURIDAD, Prioridad.ALTA,
                             "correo sospechoso de phishing", dias_desde_asignacion=15, horas_hasta_cierre=1)
    _crear_ticket_historico(creadores[1], agente_seguridad.id, Categoria.SEGURIDAD, Prioridad.ALTA,
                             "movimiento raro en mi cuenta", dias_desde_asignacion=8, horas_hasta_cierre=2)
    _crear_ticket_historico(creadores[2], agente_seguridad.id, Categoria.SEGURIDAD, Prioridad.ALTA,
                             "alguien intento entrar sin autorizacion", dias_desde_asignacion=3, horas_hasta_cierre=1.5)

    # Sandra (Redes) -- mitad y mitad
    _crear_ticket_historico(creadores[0], agente_redes.id, Categoria.REDES, Prioridad.ALTA,
                             "internet muy lento en el piso 3", dias_desde_asignacion=22, horas_hasta_cierre=6)
    _crear_ticket_historico(creadores[1], agente_redes.id, Categoria.REDES, Prioridad.ALTA,
                             "se cae la red cada 10 minutos", dias_desde_asignacion=14, horas_hasta_cierre=3)
    _crear_ticket_historico(creadores[2], agente_redes.id, Categoria.REDES, Prioridad.ALTA,
                             "sin conexion en toda la sucursal", dias_desde_asignacion=7, horas_hasta_cierre=8)
    _crear_ticket_historico(creadores[0], agente_redes.id, Categoria.REDES, Prioridad.ALTA,
                             "no carga nada desde esta mañana", dias_desde_asignacion=2, horas_hasta_cierre=1)

    # Oscar (Infraestructura) -- decente
    _crear_ticket_historico(creadores[1], agente_infra.id, Categoria.INFRAESTRUCTURA, Prioridad.MEDIA,
                             "el monitor no enciende", dias_desde_asignacion=19, horas_hasta_cierre=10)
    _crear_ticket_historico(creadores[2], agente_infra.id, Categoria.INFRAESTRUCTURA, Prioridad.MEDIA,
                             "pantalla azul constante", dias_desde_asignacion=11, horas_hasta_cierre=30)
    _crear_ticket_historico(creadores[0], agente_infra.id, Categoria.INFRAESTRUCTURA, Prioridad.MEDIA,
                             "no funciona el teclado", dias_desde_asignacion=4, horas_hasta_cierre=15)

    # Paula (Cuentas y contraseñas) -- mitad y mitad
    _crear_ticket_historico(creadores[1], agente_cuentas.id, Categoria.CUENTAS_CONTRASENAS, Prioridad.BAJA,
                             "cuenta bloqueada tras varios intentos", dias_desde_asignacion=16, horas_hasta_cierre=5)
    _crear_ticket_historico(creadores[2], agente_cuentas.id, Categoria.CUENTAS_CONTRASENAS, Prioridad.BAJA,
                             "no puedo iniciar sesion en el correo", dias_desde_asignacion=9, horas_hasta_cierre=100)

    # Ricardo (Software) -- mal desempeño: 0/3 a tiempo
    _crear_ticket_historico(creadores[0], agente_software.id, Categoria.SOFTWARE, Prioridad.BAJA,
                             "el sistema se congela al guardar", dias_desde_asignacion=25, horas_hasta_cierre=80)
    _crear_ticket_historico(creadores[1], agente_software.id, Categoria.SOFTWARE, Prioridad.BAJA,
                             "error al abrir el programa contable", dias_desde_asignacion=17, horas_hasta_cierre=90)
    _crear_ticket_historico(creadores[2], agente_software.id, Categoria.SOFTWARE, Prioridad.BAJA,
                             "no sincroniza con el servidor", dias_desde_asignacion=6, horas_hasta_cierre=76)

    # Ivan (Otros) -- excelente, pocos tickets
    _crear_ticket_historico(creadores[0], agente_otros.id, Categoria.OTROS, Prioridad.BAJA,
                             "consulta sobre politica de vacaciones", dias_desde_asignacion=13, horas_hasta_cierre=2)
    _crear_ticket_historico(creadores[1], agente_otros.id, Categoria.OTROS, Prioridad.BAJA,
                             "duda sobre horario de atencion", dias_desde_asignacion=5, horas_hasta_cierre=1)
    def _crear_ticket_sin_agente(creador_id, categoria, prioridad, texto, fecha_creacion, fecha_limite):
        """
        Ticket ABIERTO, sin agente asignado -- para probar sugerir_agente()
        contra datos reales de la demo. Bypassea ServicioTickets/GestorSLA
        (que usan datetime.now() y no permiten backdatear), mismo patron que
        _crear_ticket_historico.
        """
        ticket = Ticket(
            texto=texto,
            categoria=categoria,
            prioridad=prioridad,
            estado=EstadoTicket.ABIERTO,
            creador_id=creador_id,
            agente_id=None,
            fecha_creacion=fecha_creacion,
            fecha_limite=fecha_limite,
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket


    # --- Tickets sin agente para probar sugerir_agente() (v2.4) -----------------
    # PERMISOS: Andres (carga=1, de t1 EN_PROGRESO arriba) vs Diana (carga=0).
    # Diana deberia ganar la sugerencia pese a tener peor cumplimiento historico
    # -- la carga actual pesa antes que el desempeño pasado, por diseño.
    ahora = datetime.now()
    _crear_ticket_sin_agente(
        creadores[0], Categoria.PERMISOS, Prioridad.BAJA,
        "no puedo entrar a la vpn de la empresa",
        fecha_creacion=ahora - timedelta(hours=80),
        fecha_limite=ahora - timedelta(hours=8),  # vencido
    )

    # REDES: solo Sandra tiene esta area -- sugerencia sin ambiguedad, sirve
    # para confirmar el caso simple antes del caso con desempate de arriba.
    _crear_ticket_sin_agente(
        creadores[1], Categoria.REDES, Prioridad.ALTA,
        "la vpn se cae cada 5 minutos",
        fecha_creacion=ahora - timedelta(hours=3, minutes=50),
        fecha_limite=ahora + timedelta(minutes=10),  # proximo a vencer (<20% de ventana restante)
    )

    print("2 tickets sin agente creados (1 vencido en Permisos, 1 proximo a vencer en Redes) para probar sugerir_agente()")
        
    
    print("Historico de 26 tickets cerrados creado para poblar metricas por agente (ultimos 30 dias)")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        sembrar()