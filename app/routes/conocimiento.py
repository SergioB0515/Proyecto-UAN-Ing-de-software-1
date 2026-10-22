from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_babel import gettext as _

from app.extensions import db
from app.models.enum import Categoria, RolUsuario
from app.models.usuario import Usuario
from app.routes.decoradores import requiere_login, requiere_personal
from app.services.base_conocimiento import ServicioBaseConocimiento
from app.services.exceptions import ArticuloNoEncontradoError, ErrorPersistencia

conocimiento_bp = Blueprint("conocimiento", __name__)

ORDENES = ("recientes", "populares", "utiles")


def _es_personal():
    return session.get("rol") in (RolUsuario.ADMIN, RolUsuario.AGENTE)


def _categoria(valor):
    if not valor:
        return None
    try:
        return Categoria(valor)
    except ValueError:
        return None


@conocimiento_bp.route("/conocimiento")
@requiere_login
def inicio():
    busqueda = (request.args.get("q") or "").strip()
    categoria = _categoria(request.args.get("categoria"))
    orden = request.args.get("orden") if request.args.get("orden") in ORDENES else "recientes"
    ver_borradores = _es_personal() and request.args.get("borradores") == "1"
    articulos = ServicioBaseConocimiento.listar(
        busqueda=busqueda, categoria=categoria, incluir_borradores=ver_borradores, orden=orden,
    )
    return render_template(
        "conocimiento.html",
        articulos=articulos,
        busqueda=busqueda,
        categoria_actual=categoria.value if categoria else None,
        orden=orden,
        ver_borradores=ver_borradores,
        conteo=ServicioBaseConocimiento.conteo_por_categoria(),
        es_personal=_es_personal(),
    )


@conocimiento_bp.route("/conocimiento/<int:articulo_id>")
@requiere_login
def ver(articulo_id):
    try:
        articulo = ServicioBaseConocimiento.obtener(articulo_id, incluir_borradores=_es_personal())
    except ArticuloNoEncontradoError:
        abort(404)
    vistos = session.get("articulos_vistos", [])
    if articulo.id not in vistos:
        ServicioBaseConocimiento.registrar_vista(articulo)
        session["articulos_vistos"] = (vistos + [articulo.id])[-100:]
    autor = db.session.get(Usuario, articulo.autor_id)
    return render_template(
        "articulo.html",
        articulo=articulo,
        autor=autor,
        relacionados=ServicioBaseConocimiento.relacionados(articulo),
        mi_voto=ServicioBaseConocimiento.voto_de(articulo.id, session["usuario_id"]),
        es_personal=_es_personal(),
        desde_ticket=request.args.get("desde") == "ticket",
    )


def _formulario():
    return {
        "titulo": request.form.get("titulo"),
        "contenido": request.form.get("contenido"),
        "categoria": _categoria(request.form.get("categoria")),
        "resumen": request.form.get("resumen"),
        "etiquetas": request.form.get("etiquetas"),
        "publicado": request.form.get("publicado") == "1",
    }


@conocimiento_bp.route("/conocimiento/nuevo", methods=["GET", "POST"])
@requiere_personal
def nuevo():
    if request.method == "POST":
        datos = _formulario()
        try:
            articulo = ServicioBaseConocimiento.crear(session["usuario_id"], **datos)
            flash(_("Artículo publicado") if articulo.publicado else _("Borrador guardado"), "success")
            return redirect(url_for("conocimiento.ver", articulo_id=articulo.id))
        except (ValueError, ErrorPersistencia) as e:
            flash(str(e), "danger")
            return render_template("articulo_form.html", articulo=None, datos=request.form)
    return render_template("articulo_form.html", articulo=None, datos={"publicado": "1"})


@conocimiento_bp.route("/conocimiento/<int:articulo_id>/editar", methods=["GET", "POST"])
@requiere_personal
def editar(articulo_id):
    try:
        articulo = ServicioBaseConocimiento.obtener(articulo_id, incluir_borradores=True)
    except ArticuloNoEncontradoError:
        abort(404)
    if request.method == "POST":
        try:
            ServicioBaseConocimiento.actualizar(session["usuario_id"], articulo_id, **_formulario())
            flash(_("Artículo actualizado"), "success")
            return redirect(url_for("conocimiento.ver", articulo_id=articulo_id))
        except (ValueError, ErrorPersistencia) as e:
            flash(str(e), "danger")
            return render_template("articulo_form.html", articulo=articulo, datos=request.form)
    datos = {
        "titulo": articulo.titulo, "contenido": articulo.contenido, "categoria": articulo.categoria.value,
        "resumen": articulo.resumen or "", "etiquetas": articulo.etiquetas or "",
        "publicado": "1" if articulo.publicado else "",
    }
    return render_template("articulo_form.html", articulo=articulo, datos=datos)


@conocimiento_bp.route("/conocimiento/<int:articulo_id>/publicacion", methods=["POST"])
@requiere_personal
def publicacion(articulo_id):
    publicar = request.form.get("publicado") == "1"
    try:
        ServicioBaseConocimiento.cambiar_publicacion(session["usuario_id"], articulo_id, publicar)
        flash(_("Artículo publicado") if publicar else _("Artículo archivado"), "success")
    except (ArticuloNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("conocimiento.ver", articulo_id=articulo_id))


@conocimiento_bp.route("/conocimiento/<int:articulo_id>/votar", methods=["POST"])
@requiere_login
def votar(articulo_id):
    util = request.form.get("util") == "1"
    try:
        ServicioBaseConocimiento.votar(articulo_id, session["usuario_id"], util)
        flash(_("¡Gracias por tu valoración!"), "success")
    except (ArticuloNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("conocimiento.ver", articulo_id=articulo_id) + "#valoracion")


@conocimiento_bp.route("/conocimiento/<int:articulo_id>/resuelto", methods=["POST"])
@requiere_login
def resuelto(articulo_id):
    resueltos = session.get("articulos_resueltos", [])
    try:
        if articulo_id not in resueltos:
            ServicioBaseConocimiento.registrar_resolucion(articulo_id)
            session["articulos_resueltos"] = (resueltos + [articulo_id])[-100:]
        ServicioBaseConocimiento.votar(articulo_id, session["usuario_id"], True)
    except (ArticuloNoEncontradoError, ErrorPersistencia):
        abort(404)
    session.pop("borrador_ticket", None)
    flash(_("¡Genial! Nos alegra que lo hayas resuelto sin necesidad de abrir un ticket."), "success")
    return redirect(url_for("auth.dashboard"))


@conocimiento_bp.route("/conocimiento/sugerencias")
@requiere_login
def sugerencias():
    texto = (request.args.get("q") or "")[:1200]
    resultados = ServicioBaseConocimiento.sugerir(texto, limite=3) if len(texto.strip()) >= 12 else []
    return jsonify({"datos": [
        {
            "id": a.id,
            "titulo": a.titulo,
            "resumen": a.resumen or (a.contenido[:140] + ("…" if len(a.contenido) > 140 else "")),
            "categoria": a.categoria.value,
            "puntaje": puntaje,
            "url": url_for("conocimiento.ver", articulo_id=a.id, desde="ticket"),
        }
        for a, puntaje in resultados
    ]})


@conocimiento_bp.route("/conocimiento/vista-previa", methods=["POST"])
@requiere_personal
def vista_previa():
    from app.formato import markdown_seguro

    datos = request.get_json(silent=True) or {}
    return jsonify({"html": str(markdown_seguro((datos.get("texto") or "")[:20000]))})
