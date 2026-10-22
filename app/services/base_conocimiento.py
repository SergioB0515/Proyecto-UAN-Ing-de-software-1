import re
import unicodedata
from datetime import datetime

from flask_babel import gettext as _
from sqlalchemy import select, func, or_

from app.extensions import db
from app.models.articulo import Articulo, VotoArticulo
from app.models.enum import AccionAuditoria, Categoria
from app.services.auditoria import ServicioAuditoria
from app.services.clasificador import ClasificadorTickets
from app.services.exceptions import ArticuloNoEncontradoError, ErrorPersistencia

PALABRAS_VACIAS = {
    "a", "al", "algo", "ante", "aqui", "asi", "aun", "cada", "como", "con", "cual", "cuando", "de", "del",
    "desde", "donde", "el", "ella", "en", "entre", "era", "es", "esa", "ese", "eso", "esta", "este", "esto",
    "estoy", "fue", "ha", "hay", "hace", "la", "las", "le", "les", "lo", "los", "me", "mi", "mis", "muy",
    "nada", "ni", "no", "nos", "o", "otra", "otro", "para", "pero", "por", "porque", "puedo", "que", "se",
    "ser", "si", "sin", "sobre", "solo", "son", "su", "sus", "tambien", "tengo", "todo", "un", "una", "uno",
    "y", "ya", "yo", "hola", "favor", "ayuda", "problema", "buenas", "buenos", "dias", "tardes", "gracias",
    "the", "and", "for", "with", "my", "is", "it", "to", "of", "in", "on", "not", "can", "cant", "i",
}
PESO_TITULO = 3.0
PESO_ETIQUETA = 2.5
PESO_RESUMEN = 1.5
PESO_CONTENIDO = 0.5
BONO_CATEGORIA = 2.0
PUNTAJE_MINIMO = 3.0
LONGITUD_MINIMA_TITULO = 5
LONGITUD_MINIMA_CONTENIDO = 20


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _raiz(palabra):
    for sufijo in ("aciones", "acion", "mente", "es", "s"):
        if len(palabra) > len(sufijo) + 3 and palabra.endswith(sufijo):
            return palabra[: -len(sufijo)]
    return palabra


def terminos(texto):
    palabras = re.findall(r"[a-z0-9ñ]+", normalizar(texto))
    return {_raiz(p) for p in palabras if len(p) > 2 and p not in PALABRAS_VACIAS}


class ServicioBaseConocimiento:

    @staticmethod
    def _guardar(mensaje):
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"{mensaje}, error: {e}")
            raise ErrorPersistencia(mensaje) from e

    @staticmethod
    def _validar(titulo, contenido, categoria):
        titulo = (titulo or "").strip()
        contenido = (contenido or "").strip()
        if len(titulo) < LONGITUD_MINIMA_TITULO:
            raise ValueError(_("El título debe tener al menos %(n)s caracteres", n=LONGITUD_MINIMA_TITULO))
        if len(titulo) > 160:
            raise ValueError(_("El título no puede superar los 160 caracteres"))
        if len(contenido) < LONGITUD_MINIMA_CONTENIDO:
            raise ValueError(_("El contenido debe tener al menos %(n)s caracteres", n=LONGITUD_MINIMA_CONTENIDO))
        if not isinstance(categoria, Categoria):
            raise ValueError(_("Categoría no válida"))
        return titulo, contenido

    @staticmethod
    def _limpiar_etiquetas(etiquetas):
        vistas = []
        for e in (etiquetas or "").split(","):
            e = e.strip().lower()
            if e and e not in vistas:
                vistas.append(e[:40])
        return ", ".join(vistas[:10]) or None

    @staticmethod
    def obtener(articulo_id, incluir_borradores=False):
        articulo = db.session.get(Articulo, articulo_id)
        if articulo is None or (not articulo.publicado and not incluir_borradores):
            raise ArticuloNoEncontradoError(_("El artículo no existe"))
        return articulo

    @staticmethod
    def crear(autor_id, titulo, contenido, categoria, resumen=None, etiquetas=None, publicado=True):
        titulo, contenido = ServicioBaseConocimiento._validar(titulo, contenido, categoria)
        articulo = Articulo(
            titulo=titulo,
            contenido=contenido,
            resumen=(resumen or "").strip()[:300] or None,
            categoria=categoria,
            etiquetas=ServicioBaseConocimiento._limpiar_etiquetas(etiquetas),
            publicado=bool(publicado),
            autor_id=autor_id,
        )
        db.session.add(articulo)
        ServicioBaseConocimiento._guardar(_("No se pudo crear el artículo"))
        ServicioAuditoria.registrar(
            usuario_id=autor_id,
            accion=AccionAuditoria.CREAR_ARTICULO,
            detalle=_("Artículo #%(p1)s creado: %(p2)s", p1=articulo.id, p2=articulo.titulo),
        )
        return articulo

    @staticmethod
    def actualizar(actor_id, articulo_id, titulo, contenido, categoria, resumen=None, etiquetas=None, publicado=True):
        articulo = ServicioBaseConocimiento.obtener(articulo_id, incluir_borradores=True)
        titulo, contenido = ServicioBaseConocimiento._validar(titulo, contenido, categoria)
        articulo.titulo = titulo
        articulo.contenido = contenido
        articulo.resumen = (resumen or "").strip()[:300] or None
        articulo.categoria = categoria
        articulo.etiquetas = ServicioBaseConocimiento._limpiar_etiquetas(etiquetas)
        articulo.publicado = bool(publicado)
        articulo.fecha_actualizacion = datetime.now()
        ServicioBaseConocimiento._guardar(_("No se pudo actualizar el artículo"))
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.EDITAR_ARTICULO,
            detalle=_("Artículo #%(p1)s editado: %(p2)s", p1=articulo.id, p2=articulo.titulo),
        )
        return articulo

    @staticmethod
    def cambiar_publicacion(actor_id, articulo_id, publicado):
        articulo = ServicioBaseConocimiento.obtener(articulo_id, incluir_borradores=True)
        if articulo.publicado == publicado:
            return articulo
        articulo.publicado = publicado
        articulo.fecha_actualizacion = datetime.now()
        ServicioBaseConocimiento._guardar(_("No se pudo cambiar la publicación del artículo"))
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.PUBLICAR_ARTICULO if publicado else AccionAuditoria.ARCHIVAR_ARTICULO,
            detalle=(_("Artículo #%(p1)s publicado", p1=articulo.id) if publicado
                     else _("Artículo #%(p1)s archivado", p1=articulo.id)),
        )
        return articulo

    @staticmethod
    def listar(busqueda=None, categoria=None, incluir_borradores=False, orden="recientes"):
        query = select(Articulo)
        if not incluir_borradores:
            query = query.where(Articulo.publicado.is_(True))
        if categoria is not None:
            query = query.where(Articulo.categoria == categoria)
        if busqueda and busqueda.strip():
            patron = f"%{busqueda.strip()}%"
            query = query.where(or_(
                Articulo.titulo.ilike(patron), Articulo.contenido.ilike(patron),
                Articulo.etiquetas.ilike(patron), Articulo.resumen.ilike(patron),
            ))
        if orden == "populares":
            query = query.order_by(Articulo.vistas.desc(), Articulo.id.desc())
        elif orden == "utiles":
            query = query.order_by(Articulo.votos_utiles.desc(), Articulo.id.desc())
        else:
            query = query.order_by(Articulo.fecha_actualizacion.desc())
        articulos = db.session.execute(query).scalars().all()

        if busqueda and busqueda.strip() and not articulos:
            articulos = [a for a, _p in ServicioBaseConocimiento.sugerir(busqueda, limite=10, incluir_borradores=incluir_borradores)]
        return articulos

    @staticmethod
    def conteo_por_categoria():
        filas = db.session.execute(
            select(Articulo.categoria, func.count(Articulo.id))
            .where(Articulo.publicado.is_(True))
            .group_by(Articulo.categoria)
        ).all()
        return {c.value: n for c, n in filas}

    @staticmethod
    def puntuar(articulo, terminos_consulta, categoria_estimada=None):
        if not terminos_consulta:
            return 0.0
        puntaje = 0.0
        puntaje += PESO_TITULO * len(terminos_consulta & terminos(articulo.titulo))
        puntaje += PESO_ETIQUETA * len(terminos_consulta & terminos(articulo.etiquetas))
        puntaje += PESO_RESUMEN * len(terminos_consulta & terminos(articulo.resumen))
        puntaje += PESO_CONTENIDO * len(terminos_consulta & terminos(articulo.contenido))
        if puntaje > 0 and categoria_estimada is not None and articulo.categoria == categoria_estimada:
            puntaje += BONO_CATEGORIA
        return puntaje

    @staticmethod
    def sugerir(texto, limite=3, incluir_borradores=False):
        consulta = terminos(texto)
        if not consulta:
            return []
        categoria = ClasificadorTickets.clasificar(texto or "")
        categoria = None if categoria == Categoria.OTROS else categoria
        query = select(Articulo)
        if not incluir_borradores:
            query = query.where(Articulo.publicado.is_(True))
        candidatos = []
        for articulo in db.session.execute(query).scalars():
            puntaje = ServicioBaseConocimiento.puntuar(articulo, consulta, categoria)
            if puntaje >= PUNTAJE_MINIMO:
                candidatos.append((articulo, round(puntaje, 2)))
        candidatos.sort(key=lambda par: (-par[1], -(par[0].votos_utiles or 0), par[0].id))
        return candidatos[:limite]

    @staticmethod
    def relacionados(articulo, limite=3):
        consulta = terminos(f"{articulo.titulo} {articulo.etiquetas or ''}")
        resultado = []
        for otro in db.session.execute(
            select(Articulo).where(Articulo.publicado.is_(True), Articulo.id != articulo.id)
        ).scalars():
            puntaje = ServicioBaseConocimiento.puntuar(otro, consulta, articulo.categoria)
            if otro.categoria == articulo.categoria:
                puntaje += 1
            if puntaje > 1:
                resultado.append((otro, puntaje))
        resultado.sort(key=lambda par: -par[1])
        return [a for a, _p in resultado[:limite]]

    @staticmethod
    def registrar_vista(articulo):
        articulo.vistas = (articulo.vistas or 0) + 1
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo registrar la vista del artículo, error: {e}")

    @staticmethod
    def votar(articulo_id, usuario_id, util):
        articulo = ServicioBaseConocimiento.obtener(articulo_id)
        voto = db.session.execute(
            select(VotoArticulo).where(VotoArticulo.articulo_id == articulo.id, VotoArticulo.usuario_id == usuario_id)
        ).scalar_one_or_none()
        if voto is not None:
            if voto.util == util:
                return articulo
            if voto.util:
                articulo.votos_utiles = max(0, articulo.votos_utiles - 1)
            else:
                articulo.votos_no_utiles = max(0, articulo.votos_no_utiles - 1)
            voto.util = util
            voto.fecha = datetime.now()
        else:
            db.session.add(VotoArticulo(articulo_id=articulo.id, usuario_id=usuario_id, util=util))
        if util:
            articulo.votos_utiles += 1
        else:
            articulo.votos_no_utiles += 1
        ServicioBaseConocimiento._guardar(_("No se pudo registrar tu voto"))
        return articulo

    @staticmethod
    def voto_de(articulo_id, usuario_id):
        voto = db.session.execute(
            select(VotoArticulo.util).where(VotoArticulo.articulo_id == articulo_id, VotoArticulo.usuario_id == usuario_id)
        ).scalar_one_or_none()
        return voto

    @staticmethod
    def registrar_resolucion(articulo_id):
        articulo = ServicioBaseConocimiento.obtener(articulo_id)
        articulo.resoluciones = (articulo.resoluciones or 0) + 1
        ServicioBaseConocimiento._guardar(_("No se pudo registrar la resolución"))
        return articulo
