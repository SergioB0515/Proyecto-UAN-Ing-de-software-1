"""
Pruebas de la integracion de correo en ServicioNotificaciones.crear()

Que verifica:
1. Una plantilla en PLANTILLAS_CON_CORREO (CERRADO) dispara un correo con
   el destinatario y el texto correctos.
2. CERRADO_SIN_ATENDER tambien dispara correo (segunda plantilla del set,
   para no depender de un solo caso).
3. Las plantillas de SLA (vencido/proximo, creador/agente) disparan correo
   -- las 4 variantes.
4. Una plantilla que NO esta en el set (TRANSFERENCIA_NUEVA) no dispara
   ningun correo -- control negativo, confirma que el filtro realmente
   filtra y no manda correo para todo.

Nota de sincronizacion: _enviar_correo corre en threading.Thread para no
bloquear la request real, lo que lo hace asincrono respecto al test --
mail.record_messages() podria revisar el buzon antes de que el hilo
real termine. Se fuerza Thread.start() a ejecutar el target de forma
sincrona (mismo hilo del test) solo para esta suite, via monkeypatch --
no se mockea ningun comportamiento de negocio, mail.send() sigue
corriendo de verdad (interceptado por record_messages, no por un mock).
"""
import threading

import pytest

from app.extensions import db, mail
from app.services.autenticacion import ServicioAutenticacion
from app.services.notificaciones import ServicioNotificaciones
from app import notificaciones_i18n as notif
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario

EMAIL_ADMIN = "prueba_notif_correo_admin@empresa.com"
EMAIL_USUARIO = "prueba_notif_correo_usuario@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_USUARIO):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Notif Correo", email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN, nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Prueba Notif Correo", email=EMAIL_USUARIO,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )


@pytest.fixture(autouse=True)
def hilos_sincronos(monkeypatch):
    def start_sincrono(self):
        self.run()
    monkeypatch.setattr(threading.Thread, "start", start_sincrono)


@pytest.mark.parametrize("plantilla", [
    notif.CERRADO,
    notif.CERRADO_SIN_ATENDER,
    notif.SLA_PROXIMO_CREADOR,
    notif.SLA_PROXIMO_AGENTE,
    notif.SLA_VENCIDO_CREADOR,
    notif.SLA_VENCIDO_AGENTE,
])
def test_plantilla_con_correo_envia(plantilla):
    usuario = Usuario.query.filter_by(email=EMAIL_USUARIO).first()

    with mail.record_messages() as buzon:
        ServicioNotificaciones.crear(usuario_id=usuario.id, mensaje=plantilla, ticket_id=77)

    assert len(buzon) == 1, (
        f"se esperaba 1 correo para la plantilla '{plantilla}', se obtuvieron {len(buzon)}"
    )
    assert buzon[0].recipients == [usuario.email]
    assert "77" in buzon[0].body


def test_plantilla_sin_correo_no_envia():
    usuario = Usuario.query.filter_by(email=EMAIL_USUARIO).first()

    with mail.record_messages() as buzon:
        ServicioNotificaciones.crear(usuario_id=usuario.id, mensaje=notif.TRANSFERENCIA_NUEVA, ticket_id=88)

    assert len(buzon) == 0, (
        f"TRANSFERENCIA_NUEVA no deberia disparar correo, se obtuvieron {len(buzon)}"
    )