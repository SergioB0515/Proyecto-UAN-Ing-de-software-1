from functools import wraps

from flask import Blueprint, g, jsonify, request, render_template, session, url_for, redirect, flash
from flask_babel import gettext as _
from sqlalchemy import select

from app.extensions import db
from app.models.enum import Categoria, EstadoTicket, Prioridad, RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.routes.decoradores import requiere_login
from app.services.adjuntos import ServicioAdjuntos
from app.services.base_conocimiento import ServicioBaseConocimiento
from app.services.exceptions import (
    ArticuloNoEncontradoError,
    ComentarioVacioError,
    ErrorPersistencia,
    PermisoDenegadoError,
    TicketNoEncontradoError,
    TokenApiInvalidoError,
)
from app.services.permisos import ServicioPermisos
from app.services.tickets import ServicioTickets
from app.services.tokens_api import ServicioTokensApi, limitador, LIMITE_PETICIONES_POR_MINUTO, DURACIONES_DIAS
from app.version import VERSION

api_bp = Blueprint("api", __name__)

MAX_POR_PAGINA = 100


def error(codigo, mensaje, estado):
    respuesta = jsonify({"error": {"codigo": codigo, "mensaje": mensaje}})
    respuesta.status_code = estado
    return respuesta


def requiere_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        crudo = cabecera[7:].strip() if cabecera.lower().startswith("bearer ") else ""
        try:
            token, usuario = ServicioTokensApi.autenticar(crudo)
        except TokenApiInvalidoError as e:
            respuesta = error("no_autorizado", str(e), 401)
            respuesta.headers["WWW-Authenticate"] = 'Bearer realm="api"'
            return respuesta
        permitido, espera = limitador.permitir(token.id)
        if not permitido:
            respuesta = error("demasiadas_peticiones", _("Límite de peticiones alcanzado"), 429)
            respuesta.headers["Retry-After"] = str(espera)
            return respuesta
        g.api_token = token
        g.api_usuario = usuario
        respuesta = func(*args, **kwargs)
        respuesta.headers["X-RateLimit-Limit"] = str(LIMITE_PETICIONES_POR_MINUTO)
        respuesta.headers["X-RateLimit-Remaining"] = str(limitador.restantes(token.id))
        return respuesta
    return wrapper


def _fecha(valor):
    return valor.isoformat(timespec="seconds") if valor else None


def ticket_a_dict(ticket, nombres=None):
    nombres = nombres or {}
    return {
        "id": ticket.id,
        "texto": ticket.texto,
        "categoria": ticket.categoria.value,
        "prioridad": ticket.prioridad.value,
        "estado": ticket.estado.value,
        "creador": {"id": ticket.creador_id, "nombre": nombres.get(ticket.creador_id)},
        "agente": {"id": ticket.agente_id, "nombre": nombres.get(ticket.agente_id)} if ticket.agente_id else None,
        "fecha_creacion": _fecha(ticket.fecha_creacion),
        "fecha_limite": _fecha(ticket.fecha_limite),
        "fecha_asignacion": _fecha(ticket.fecha_asignacion),
        "fecha_cierre": _fecha(ticket.fecha_cierre),
        "url": url_for("tickets.detalle", ticket_id=ticket.id, _external=True),
    }


def _nombres(ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(db.session.execute(select(Usuario.id, Usuario.nombre).where(Usuario.id.in_(ids))).all())


def _enum_param(nombre, clase):
    valor = request.args.get(nombre)
    if not valor:
        return None
    try:
        return clase(valor)
    except ValueError:
        raise ValueError(nombre)


@api_bp.route("/api/v1/yo")
@requiere_token
def yo():
    u = g.api_usuario
    return jsonify({
        "id": u.id,
        "nombre": u.nombre,
        "email": u.email,
        "rol": u.rol.value,
        "nivel": u.nivel.value,
        "area_soporte": u.area_soporte.value if u.area_soporte else None,
        "token": {"nombre": g.api_token.nombre, "expira": _fecha(g.api_token.expira)},
    })


@api_bp.route("/api/v1/tickets", methods=["GET"])
@requiere_token
def listar_tickets():
    u = g.api_usuario
    try:
        estado = _enum_param("estado", EstadoTicket)
        categoria = _enum_param("categoria", Categoria)
        prioridad = _enum_param("prioridad", Prioridad)
    except ValueError as e:
        return error("parametro_invalido", _("Valor no válido para «%(p)s»", p=str(e)), 400)
    pagina = max(request.args.get("pagina", 1, type=int) or 1, 1)
    por_pagina = min(max(request.args.get("por_pagina", 20, type=int) or 20, 1), MAX_POR_PAGINA)

    query = select(Ticket)
    if u.rol == RolUsuario.FINAL:
        query = query.where(Ticket.creador_id == u.id)
    elif u.rol == RolUsuario.AGENTE:
        query = query.where((Ticket.categoria == u.area_soporte) | (Ticket.agente_id == u.id) | (Ticket.creador_id == u.id))
    if estado is not None:
        query = query.where(Ticket.estado == estado)
    if categoria is not None:
        query = query.where(Ticket.categoria == categoria)
    if prioridad is not None:
        query = query.where(Ticket.prioridad == prioridad)
    paginado = db.paginate(query.order_by(Ticket.fecha_creacion.desc()), page=pagina, per_page=por_pagina, error_out=False)
    nombres = _nombres({t.creador_id for t in paginado.items} | {t.agente_id for t in paginado.items})
    return jsonify({
        "datos": [ticket_a_dict(t, nombres) for t in paginado.items],
        "paginacion": {"pagina": paginado.page, "por_pagina": por_pagina, "total": paginado.total, "paginas": paginado.pages},
    })


@api_bp.route("/api/v1/tickets", methods=["POST"])
@requiere_token
def crear_ticket():
    datos = request.get_json(silent=True) or {}
    texto = (datos.get("texto") or "").strip()
    if len(texto) < 10:
        return error("validacion", _("El campo «texto» es obligatorio (mínimo 10 caracteres)"), 422)
    if len(texto) > 1200:
        return error("validacion", _("El campo «texto» no puede superar 1200 caracteres"), 422)
    try:
        ticket = ServicioTickets.crear_ticket(creador=g.api_usuario, texto=texto)
    except ErrorPersistencia as e:
        return error("error_interno", str(e), 500)
    respuesta = jsonify(ticket_a_dict(ticket, _nombres({ticket.creador_id})))
    respuesta.status_code = 201
    respuesta.headers["Location"] = url_for("api.obtener_ticket", ticket_id=ticket.id, _external=True)
    return respuesta


def _ticket_visible(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None or not ServicioPermisos.puede_ver_ticket(g.api_usuario, ticket):
        return None
    return ticket


@api_bp.route("/api/v1/tickets/<int:ticket_id>", methods=["GET"])
@requiere_token
def obtener_ticket(ticket_id):
    ticket = _ticket_visible(ticket_id)
    if ticket is None:
        return error("no_encontrado", _("El ticket no existe o no tienes acceso"), 404)
    internos = ServicioPermisos.puede_ver_internos(g.api_usuario)
    comentarios = ServicioTickets.listar_comentarios(ticket.id, incluir_internos=internos)
    adjuntos = ServicioAdjuntos.listar(ticket.id)
    nombres = _nombres({ticket.creador_id, ticket.agente_id} | {c.autor_id for c in comentarios})
    cuerpo = ticket_a_dict(ticket, nombres)
    cuerpo["comentarios"] = [
        {"id": c.id, "autor": {"id": c.autor_id, "nombre": nombres.get(c.autor_id)}, "texto": c.texto,
         "interno": bool(c.interno), "fecha": _fecha(c.fecha)}
        for c in comentarios
    ]
    cuerpo["adjuntos"] = [
        {"id": a.id, "nombre": a.nombre_original, "tipo": a.tipo_mime, "tamano": a.tamano, "fecha": _fecha(a.fecha),
         "url": url_for("colaboracion.descargar_adjunto", adjunto_id=a.id, _external=True)}
        for a in adjuntos
    ]
    return jsonify(cuerpo)


@api_bp.route("/api/v1/tickets/<int:ticket_id>/comentarios", methods=["POST"])
@requiere_token
def comentar(ticket_id):
    ticket = _ticket_visible(ticket_id)
    if ticket is None:
        return error("no_encontrado", _("El ticket no existe o no tienes acceso"), 404)
    datos = request.get_json(silent=True) or {}
    try:
        comentario = ServicioTickets.agregar_comentario(
            ticket_id=ticket.id, autor_id=g.api_usuario.id,
            texto=(datos.get("texto") or ""), interno=bool(datos.get("interno", False)),
        )
    except ComentarioVacioError as e:
        return error("validacion", str(e), 422)
    except PermisoDenegadoError as e:
        return error("prohibido", str(e), 403)
    except (TicketNoEncontradoError, ErrorPersistencia) as e:
        return error("error_interno", str(e), 500)
    respuesta = jsonify({"id": comentario.id, "texto": comentario.texto, "interno": comentario.interno,
                         "fecha": _fecha(comentario.fecha)})
    respuesta.status_code = 201
    return respuesta


@api_bp.route("/api/v1/articulos", methods=["GET"])
@requiere_token
def articulos():
    try:
        categoria = _enum_param("categoria", Categoria)
    except ValueError as e:
        return error("parametro_invalido", _("Valor no válido para «%(p)s»", p=str(e)), 400)
    lista = ServicioBaseConocimiento.listar(busqueda=request.args.get("q"), categoria=categoria)
    return jsonify({"datos": [
        {"id": a.id, "titulo": a.titulo, "resumen": a.resumen, "categoria": a.categoria.value,
         "etiquetas": a.lista_etiquetas, "actualizado": _fecha(a.fecha_actualizacion),
         "url": url_for("conocimiento.ver", articulo_id=a.id, _external=True)}
        for a in lista[:50]
    ]})


@api_bp.route("/api/v1/articulos/<int:articulo_id>", methods=["GET"])
@requiere_token
def articulo(articulo_id):
    try:
        a = ServicioBaseConocimiento.obtener(articulo_id)
    except ArticuloNoEncontradoError as e:
        return error("no_encontrado", str(e), 404)
    return jsonify({"id": a.id, "titulo": a.titulo, "resumen": a.resumen, "contenido": a.contenido,
                    "categoria": a.categoria.value, "etiquetas": a.lista_etiquetas,
                    "actualizado": _fecha(a.fecha_actualizacion)})


@api_bp.route("/api/v1/metricas", methods=["GET"])
@requiere_token
def metricas():
    if g.api_usuario.rol != RolUsuario.ADMIN:
        return error("prohibido", _("Solo administradores"), 403)
    from app.services.analitica import ServicioAnalitica

    datos = ServicioAnalitica.panel(dias=request.args.get("dias", 30))
    return jsonify({
        "periodo_dias": datos["dias"],
        "kpis": datos["kpis"],
        "variaciones": datos["variaciones"],
        "backlog": datos["backlog"],
        "vencidos": datos["vencidos"],
        "csat": datos["csat"],
        "por_categoria": datos["por_categoria"],
    })


@api_bp.route("/api/v1/<path:_resto>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def no_encontrado(_resto):
    return error("no_encontrado", _("Recurso no encontrado"), 404)


@api_bp.route("/api/docs")
@requiere_login
def docs():
    from app.services.tokens_api import MAX_TOKENS_ACTIVOS

    return render_template(
        "api_docs.html",
        version=VERSION,
        tokens=ServicioTokensApi.listar(session["usuario_id"]),
        token_nuevo=session.pop("token_api_nuevo", None),
        duraciones=DURACIONES_DIAS,
        max_tokens=MAX_TOKENS_ACTIVOS,
        limite=LIMITE_PETICIONES_POR_MINUTO,
    )


@api_bp.route("/api/tokens", methods=["POST"])
@requiere_login
def crear_token():
    dias = request.form.get("dias", type=int)
    try:
        _token, crudo = ServicioTokensApi.crear(session["usuario_id"], request.form.get("nombre"), dias=dias or None)
        session["token_api_nuevo"] = crudo
        flash(_("Token creado. Cópialo ahora: no se volverá a mostrar."), "success")
    except (ValueError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("api.docs") + "#tokens")


@api_bp.route("/api/tokens/<int:token_id>/revocar", methods=["POST"])
@requiere_login
def revocar_token(token_id):
    try:
        ServicioTokensApi.revocar(session["usuario_id"], token_id)
        flash(_("Token revocado"), "success")
    except (TokenApiInvalidoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("api.docs") + "#tokens")
