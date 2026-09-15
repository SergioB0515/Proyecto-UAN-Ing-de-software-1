"""
Genera una previsualizacion en HTML de todos los correos que envia la app y
los ENVIA DE VERDAD (por SMTP, usando las credenciales MAIL_USERNAME /
MAIL_PASSWORD de tu .env) a DESTINATARIO_PREVIEW, ademas de guardar una
copia de cada uno en disco para revisarlos sin depender del correo.

Uso:
    venv/Scripts/python.exe -m app.scripts.previsualizar_correos
"""
import os
import threading
import webbrowser
from datetime import datetime, timedelta

DESTINATARIO_PREVIEW = "ticketssoporte057@gmail.com"

os.environ.setdefault("SECRET_KEY", "clave-previsualizacion-correos")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# TESTING="false" (a diferencia de los tests) para que MAIL_SUPPRESS_SEND
# quede en False y el correo se mande de verdad por SMTP.
os.environ["TESTING"] = "false"
os.environ["SCHEDULER_ACTIVO"] = "0"
os.environ["CLASIFICADOR_ML_ACTIVO"] = "0"

# El envio real corre en threading.Thread para no bloquear la request; para
# esta previsualizacion lo forzamos a ejecutar sincronicamente (mismo patron
# que tests/test_notificaciones_correo.py) asi mail.record_messages() ve el
# correo antes de seguir.
threading.Thread.start = lambda self: self.run()

from app import create_app
from app.extensions import db, mail
from app.services.autenticacion import ServicioAutenticacion
from app.services.notificaciones import ServicioNotificaciones
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, Prioridad
from app import notificaciones_i18n as notif

CARPETA_SALIDA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "correos_preview"
)
CARPETA_SALIDA = os.path.abspath(CARPETA_SALIDA)

# (plantilla, nombre de archivo, estado que debe tener el ticket para que la
# previsualizacion tenga sentido)
PLANTILLAS_A_PROBAR = [
    (notif.CERRADO, "cerrado", EstadoTicket.CERRADO),
    (notif.CERRADO_SIN_ATENDER, "cerrado_sin_atender", EstadoTicket.CERRADO),
    (notif.SLA_PROXIMO_CREADOR, "sla_proximo_creador", EstadoTicket.EN_PROGRESO),
    (notif.SLA_PROXIMO_AGENTE, "sla_proximo_agente", EstadoTicket.EN_PROGRESO),
    (notif.SLA_VENCIDO_CREADOR, "sla_vencido_creador", EstadoTicket.EN_PROGRESO),
    (notif.SLA_VENCIDO_AGENTE, "sla_vencido_agente", EstadoTicket.EN_PROGRESO),
]


def _obtener_o_crear(email, **datos):
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario is not None:
        return usuario
    usuario = Usuario(email=email, **datos)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def main():
    app = create_app()
    os.makedirs(CARPETA_SALIDA, exist_ok=True)

    with app.app_context():
        db.create_all()

        admin = _obtener_o_crear(
            "preview_admin@empresa.com",
            nombre="Admin Preview",
            contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
            rol=RolUsuario.ADMIN, nivel=NivelUsuario.NORMAL,
        )
        agente = _obtener_o_crear(
            "preview_agente@empresa.com",
            nombre="Camila Rios",
            contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
            rol=RolUsuario.AGENTE, nivel=NivelUsuario.NORMAL, area_soporte=Categoria.SOFTWARE,
        )
        creador = Usuario.query.filter_by(email=DESTINATARIO_PREVIEW).first()
        if creador is None:
            creador = ServicioAutenticacion.registrar(
                nombre="Usuario Preview", email=DESTINATARIO_PREVIEW,
                contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
                nivel=NivelUsuario.NORMAL, admin_id=admin.id,
            )

        ticket = Ticket(
            texto="El programa de facturación no abre desde ayer, ya reinicié el equipo "
                  "y el problema sigue exactamente igual.",
            categoria=Categoria.SOFTWARE, prioridad=Prioridad.ALTA, estado=EstadoTicket.EN_PROGRESO,
            creador_id=creador.id, agente_id=agente.id,
            fecha_asignacion=datetime.now() - timedelta(hours=5),
            fecha_creacion=datetime.now() - timedelta(hours=6),
            fecha_limite=datetime.now() + timedelta(hours=2),
        )
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id

        print(
            f"Enviando {len(PLANTILLAS_A_PROBAR)} correos REALES a {DESTINATARIO_PREVIEW} "
            f"y guardando una copia en:\n  {CARPETA_SALIDA}\n"
        )

        generados = []
        for plantilla, nombre_archivo, estado_ticket in PLANTILLAS_A_PROBAR:
            ticket.estado = estado_ticket
            db.session.add(ticket)
            db.session.commit()

            with mail.record_messages() as buzon:
                ServicioNotificaciones.crear(
                    usuario_id=creador.id, mensaje=plantilla, ticket_id=ticket_id,
                )

            if not buzon or buzon[0].html is None:
                print(f"  [!] {plantilla} no genero correo HTML (revisa PLANTILLAS_CON_CORREO)")
                continue

            correo = buzon[0]
            ruta = os.path.join(CARPETA_SALIDA, f"{nombre_archivo}.html")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(correo.html)
            print(f"  OK   {nombre_archivo}.html   asunto: {correo.subject}")
            generados.append((nombre_archivo, correo.subject))

        db.session.delete(ticket)
        db.session.commit()

    indice = os.path.join(CARPETA_SALIDA, "index.html")
    with open(indice, "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset='utf-8'><title>Previsualización de correos</title>")
        f.write(
            "<body style=\"margin:0;padding:2rem;background:#0a0c1e;color:#e8e6f7;"
            "font-family:'Segoe UI',Helvetica,Arial,sans-serif;\">"
        )
        f.write("<h1 style='color:#f5f3ff;'>Previsualización de correos</h1>")
        f.write("<ul style='line-height:2.2;font-size:1.05rem;'>")
        for nombre_archivo, asunto in generados:
            f.write(
                f"<li><a style='color:#8f82f5' href='{nombre_archivo}.html'>{nombre_archivo}</a>"
                f" &mdash; <span style='color:#9d9ac4'>{asunto}</span></li>"
            )
        f.write("</ul></body>")

    print(f"\nAbrí este archivo en tu navegador para ver todos los correos:\n  {indice}")

    try:
        webbrowser.open(f"file://{indice}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
