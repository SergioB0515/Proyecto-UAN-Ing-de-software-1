import hashlib
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from flask_babel import gettext as _
from sqlalchemy import select, func

from app.extensions import db
from app.models.enum import AccionAuditoria
from app.models.token_api import TokenApi
from app.models.usuario import Usuario
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import ErrorPersistencia, TokenApiInvalidoError

PREFIJO = "tk_"
MAX_TOKENS_ACTIVOS = 5
DURACIONES_DIAS = (7, 30, 90, 365)
LIMITE_PETICIONES_POR_MINUTO = 120


class LimitadorPeticiones:

    def __init__(self, limite, ventana_segundos=60):
        self.limite = limite
        self.ventana = ventana_segundos
        self._registros = {}
        self._lock = threading.Lock()

    def permitir(self, clave, ahora=None):
        ahora = time.monotonic() if ahora is None else ahora
        with self._lock:
            cola = self._registros.setdefault(clave, deque())
            while cola and cola[0] <= ahora - self.ventana:
                cola.popleft()
            if len(cola) >= self.limite:
                return False, int(cola[0] + self.ventana - ahora) + 1
            cola.append(ahora)
            return True, 0

    def restantes(self, clave):
        with self._lock:
            return max(0, self.limite - len(self._registros.get(clave, ())))


limitador = LimitadorPeticiones(LIMITE_PETICIONES_POR_MINUTO)


class ServicioTokensApi:

    @staticmethod
    def _hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def listar(usuario_id):
        return db.session.execute(
            select(TokenApi).where(TokenApi.usuario_id == usuario_id).order_by(TokenApi.revocado, TokenApi.fecha_creacion.desc())
        ).scalars().all()

    @staticmethod
    def activos(usuario_id):
        ahora = datetime.now()
        return db.session.execute(
            select(func.count(TokenApi.id)).where(
                TokenApi.usuario_id == usuario_id, TokenApi.revocado.is_(False),
                (TokenApi.expira.is_(None)) | (TokenApi.expira > ahora),
            )
        ).scalar()

    @staticmethod
    def crear(usuario_id, nombre, dias=90):
        nombre = (nombre or "").strip()
        if len(nombre) < 3 or len(nombre) > 80:
            raise ValueError(_("El nombre del token debe tener entre 3 y 80 caracteres"))
        if dias is not None and dias not in DURACIONES_DIAS:
            raise ValueError(_("Duración no válida"))
        if ServicioTokensApi.activos(usuario_id) >= MAX_TOKENS_ACTIVOS:
            raise ValueError(_("Alcanzaste el máximo de %(n)s tokens activos. Revoca alguno antes de crear otro.", n=MAX_TOKENS_ACTIVOS))

        crudo = PREFIJO + secrets.token_urlsafe(32)
        token = TokenApi(
            usuario_id=usuario_id,
            nombre=nombre,
            prefijo=crudo[:10],
            token_hash=ServicioTokensApi._hash(crudo),
            expira=datetime.now() + timedelta(days=dias) if dias else None,
        )
        db.session.add(token)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo crear el token de API, error: {e}")
            raise ErrorPersistencia(_("No se pudo crear el token")) from e
        ServicioAuditoria.registrar(
            usuario_id=usuario_id,
            accion=AccionAuditoria.CREAR_TOKEN_API,
            detalle=_("Token de API «%(p1)s» creado (%(p2)s…)", p1=nombre, p2=token.prefijo),
        )
        return token, crudo

    @staticmethod
    def revocar(usuario_id, token_id):
        token = db.session.get(TokenApi, token_id)
        if token is None or token.usuario_id != usuario_id:
            raise TokenApiInvalidoError(_("El token no existe"))
        if token.revocado:
            return token
        token.revocado = True
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise ErrorPersistencia(_("No se pudo revocar el token")) from e
        ServicioAuditoria.registrar(
            usuario_id=usuario_id,
            accion=AccionAuditoria.REVOCAR_TOKEN_API,
            detalle=_("Token de API «%(p1)s» revocado", p1=token.nombre),
        )
        return token

    @staticmethod
    def autenticar(crudo):
        if not crudo or not crudo.startswith(PREFIJO):
            raise TokenApiInvalidoError(_("Token ausente o con formato inválido"))
        token = db.session.execute(
            select(TokenApi).where(TokenApi.token_hash == ServicioTokensApi._hash(crudo))
        ).scalar_one_or_none()
        if token is None or not token.vigente:
            raise TokenApiInvalidoError(_("Token inválido, revocado o expirado"))
        usuario = db.session.get(Usuario, token.usuario_id)
        if usuario is None or not usuario.activo:
            raise TokenApiInvalidoError(_("La cuenta asociada al token no está activa"))
        ahora = datetime.now()
        if token.ultimo_uso is None or (ahora - token.ultimo_uso).total_seconds() > 60:
            token.ultimo_uso = ahora
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return token, usuario
