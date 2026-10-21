import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import select

from app.extensions import db
from app.models.doble_factor import DobleFactor
from app.models.enum import AccionAuditoria
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    CodigoInvalidoError,
    DobleFactorBloqueadoError,
    DobleFactorNoConfiguradoError,
    DobleFactorYaActivoError,
    ErrorPersistencia,
)

EMISOR = "Tickets IT"
PERIODO_SEGUNDOS = 30
DIGITOS = 6
VENTANA_PASOS = 1
CANTIDAD_CODIGOS_RESPALDO = 8
MAX_INTENTOS_FALLIDOS = 5
MINUTOS_BLOQUEO = 15
ALFABETO_RESPALDO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class ServicioDobleFactor:

    @staticmethod
    def generar_secreto():
        return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")

    @staticmethod
    def _hotp(secreto, contador):
        relleno = "=" * (-len(secreto) % 8)
        clave = base64.b32decode(secreto + relleno, casefold=True)
        resumen = hmac.new(clave, struct.pack(">Q", contador), hashlib.sha1).digest()
        desplazamiento = resumen[-1] & 0x0F
        valor = struct.unpack(">I", resumen[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
        return str(valor % (10 ** DIGITOS)).zfill(DIGITOS)

    @staticmethod
    def codigo_totp(secreto, instante=None):
        instante = time.time() if instante is None else instante
        return ServicioDobleFactor._hotp(secreto, int(instante // PERIODO_SEGUNDOS))

    @staticmethod
    def _paso_valido(secreto, codigo, instante, ultimo_paso):
        paso_actual = int(instante // PERIODO_SEGUNDOS)
        for desfase in range(-VENTANA_PASOS, VENTANA_PASOS + 1):
            paso = paso_actual + desfase
            if paso < 0 or (ultimo_paso is not None and paso <= ultimo_paso):
                continue
            if hmac.compare_digest(ServicioDobleFactor._hotp(secreto, paso), codigo):
                return paso
        return None

    @staticmethod
    def uri_aprovisionamiento(secreto, email):
        etiqueta = quote(f"{EMISOR}:{email}")
        return (
            f"otpauth://totp/{etiqueta}?secret={secreto}&issuer={quote(EMISOR)}"
            f"&algorithm=SHA1&digits={DIGITOS}&period={PERIODO_SEGUNDOS}"
        )

    @staticmethod
    def _hash_respaldo(codigo):
        clave = (current_app.config.get("SECRET_KEY") or "").encode("utf-8")
        return hmac.new(clave, codigo.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _normalizar(codigo):
        return "".join(c for c in (codigo or "").upper() if c.isalnum())

    @staticmethod
    def _generar_codigos_respaldo():
        codigos = []
        for _i in range(CANTIDAD_CODIGOS_RESPALDO):
            crudo = "".join(secrets.choice(ALFABETO_RESPALDO) for _j in range(8))
            codigos.append(f"{crudo[:4]}-{crudo[4:]}")
        return codigos

    @staticmethod
    def obtener_registro(usuario_id):
        return db.session.execute(
            select(DobleFactor).where(DobleFactor.usuario_id == usuario_id)
        ).scalar_one_or_none()

    @staticmethod
    def esta_activo(usuario_id):
        registro = ServicioDobleFactor.obtener_registro(usuario_id)
        return registro is not None and registro.activo

    @staticmethod
    def codigos_restantes(usuario_id):
        registro = ServicioDobleFactor.obtener_registro(usuario_id)
        if registro is None or not registro.activo:
            return 0
        return len(json.loads(registro.codigos_respaldo or "[]"))

    @staticmethod
    def _guardar(mensaje_error):
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"{mensaje_error}, error: {e}")
            raise ErrorPersistencia(mensaje_error) from e

    @staticmethod
    def iniciar_configuracion(usuario):
        registro = ServicioDobleFactor.obtener_registro(usuario.id)
        if registro is not None and registro.activo:
            raise DobleFactorYaActivoError(_("La verificación en dos pasos ya está activa"))

        secreto = ServicioDobleFactor.generar_secreto()
        if registro is None:
            registro = DobleFactor(usuario_id=usuario.id, secreto=secreto, activo=False)
            db.session.add(registro)
        else:
            registro.secreto = secreto
            registro.codigos_respaldo = "[]"
            registro.ultimo_paso = None
            registro.intentos_fallidos = 0
            registro.bloqueado_hasta = None

        ServicioDobleFactor._guardar(_("No se pudo iniciar la configuración de la verificación en dos pasos"))
        return secreto, ServicioDobleFactor.uri_aprovisionamiento(secreto, usuario.email)

    @staticmethod
    def configuracion_pendiente(usuario):
        registro = ServicioDobleFactor.obtener_registro(usuario.id)
        if registro is None or registro.activo:
            return None
        return registro.secreto, ServicioDobleFactor.uri_aprovisionamiento(registro.secreto, usuario.email)

    @staticmethod
    def confirmar_configuracion(usuario, codigo, instante=None):
        registro = ServicioDobleFactor.obtener_registro(usuario.id)
        if registro is None:
            raise DobleFactorNoConfiguradoError(_("Primero inicia la configuración de la verificación en dos pasos"))
        if registro.activo:
            raise DobleFactorYaActivoError(_("La verificación en dos pasos ya está activa"))

        instante = time.time() if instante is None else instante
        paso = ServicioDobleFactor._paso_valido(registro.secreto, ServicioDobleFactor._normalizar(codigo), instante, None)
        if paso is None:
            raise CodigoInvalidoError(_("El código no es válido. Revisa que la hora de tu teléfono esté sincronizada."))

        codigos = ServicioDobleFactor._generar_codigos_respaldo()
        registro.activo = True
        registro.ultimo_paso = paso
        registro.fecha_activacion = datetime.now()
        registro.codigos_respaldo = json.dumps([ServicioDobleFactor._hash_respaldo(ServicioDobleFactor._normalizar(c)) for c in codigos])
        ServicioDobleFactor._guardar(_("No se pudo activar la verificación en dos pasos"))

        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.ACTIVAR_2FA,
            detalle=_("Se activó la verificación en dos pasos para %(p1)s", p1=usuario.email),
        )
        return codigos

    @staticmethod
    def verificar(usuario_id, codigo, instante=None):
        registro = ServicioDobleFactor.obtener_registro(usuario_id)
        if registro is None or not registro.activo:
            raise DobleFactorNoConfiguradoError(_("La verificación en dos pasos no está activa"))

        ahora = datetime.now()
        if registro.bloqueado_hasta is not None and registro.bloqueado_hasta > ahora:
            raise DobleFactorBloqueadoError(_("Demasiados códigos incorrectos. Intenta de nuevo en unos minutos."))

        normalizado = ServicioDobleFactor._normalizar(codigo)
        instante = time.time() if instante is None else instante
        uso_respaldo = False

        if len(normalizado) == DIGITOS and normalizado.isdigit():
            paso = ServicioDobleFactor._paso_valido(registro.secreto, normalizado, instante, registro.ultimo_paso)
            valido = paso is not None
            if valido:
                registro.ultimo_paso = paso
        else:
            hashes = json.loads(registro.codigos_respaldo or "[]")
            buscado = ServicioDobleFactor._hash_respaldo(normalizado)
            coincidencia = next((h for h in hashes if hmac.compare_digest(h, buscado)), None)
            valido = coincidencia is not None
            if valido:
                hashes.remove(coincidencia)
                registro.codigos_respaldo = json.dumps(hashes)
                uso_respaldo = True

        if not valido:
            registro.intentos_fallidos += 1
            if registro.intentos_fallidos >= MAX_INTENTOS_FALLIDOS:
                registro.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
                registro.intentos_fallidos = 0
            ServicioDobleFactor._guardar(_("No se pudo registrar el intento de verificación"))
            ServicioAuditoria.registrar(
                usuario_id=usuario_id,
                accion=AccionAuditoria.VERIFICACION_2FA_FALLIDA,
                detalle=_("Código de verificación en dos pasos incorrecto"),
            )
            raise CodigoInvalidoError(_("El código no es válido"))

        registro.intentos_fallidos = 0
        registro.bloqueado_hasta = None
        ServicioDobleFactor._guardar(_("No se pudo completar la verificación en dos pasos"))

        if uso_respaldo:
            ServicioAuditoria.registrar(
                usuario_id=usuario_id,
                accion=AccionAuditoria.USO_CODIGO_RESPALDO,
                detalle=_("Se usó un código de respaldo (quedan %(p1)s)", p1=len(json.loads(registro.codigos_respaldo))),
            )
        return True

    @staticmethod
    def regenerar_codigos_respaldo(usuario, codigo, instante=None):
        ServicioDobleFactor.verificar(usuario.id, codigo, instante)
        registro = ServicioDobleFactor.obtener_registro(usuario.id)
        codigos = ServicioDobleFactor._generar_codigos_respaldo()
        registro.codigos_respaldo = json.dumps([ServicioDobleFactor._hash_respaldo(ServicioDobleFactor._normalizar(c)) for c in codigos])
        ServicioDobleFactor._guardar(_("No se pudieron regenerar los códigos de respaldo"))
        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.REGENERAR_CODIGOS_RESPALDO,
            detalle=_("Se regeneraron los códigos de respaldo de %(p1)s", p1=usuario.email),
        )
        return codigos

    @staticmethod
    def desactivar(usuario, contrasena):
        from app.services.autenticacion import ServicioAutenticacion

        if not contrasena or not ServicioAutenticacion._verificar_contrasena(contrasena, usuario.contrasena_hash):
            raise ValueError(_("la contraseña actual es incorrecta"))

        registro = ServicioDobleFactor.obtener_registro(usuario.id)
        if registro is None or not registro.activo:
            raise DobleFactorNoConfiguradoError(_("La verificación en dos pasos no está activa"))

        db.session.delete(registro)
        ServicioDobleFactor._guardar(_("No se pudo desactivar la verificación en dos pasos"))
        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.DESACTIVAR_2FA,
            detalle=_("Se desactivó la verificación en dos pasos para %(p1)s", p1=usuario.email),
        )
        return True
