"""Busqueda unica sobre tickets, articulos y usuarios.

La paleta de comandos (Ctrl + K) resuelve la navegacion entre paginas y el
salto a un ticket por numero, pero todo eso ocurre en el navegador y solo ve
los nombres de las paginas. Esta busqueda corre en el servidor y ve el
contenido: el texto de los tickets, los articulos y, para un administrador,
las cuentas.

Cada resultado pasa por el mismo control de acceso que su pagina: los tickets
se filtran con ServicioPermisos.puede_ver_ticket, los articulos en borrador
solo los ve el personal y los usuarios solo el administrador. Una busqueda que
devolviera titulos que el usuario no puede abrir seria una fuga de
informacion aunque el enlace diera 403.
"""

from sqlalchemy import or_, select

from app.extensions import db
from app.models.articulo import Articulo
from app.models.enum import RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.permisos import ServicioPermisos

LIMITE_POR_GRUPO = 10
MIN_TERMINO = 2


class ServicioBusqueda:

    @staticmethod
    def buscar(usuario, termino, limite=LIMITE_POR_GRUPO):
        """Devuelve un dict con las tres listas y el total encontrado."""
        termino = (termino or "").strip()
        resultado = {
            "termino": termino,
            "tickets": [],
            "articulos": [],
            "usuarios": [],
            "total": 0,
            "termino_corto": False,
        }

        # Un numero de ticket es un termino valido por si solo: "#7" es tan
        # especifico como una palabra larga, y exigirle MIN_TERMINO dejaria sin
        # buscar los primeros tickets de la instalacion.
        nucleo = termino.lstrip("#").strip()
        if usuario is None or (len(nucleo) < MIN_TERMINO and not nucleo.isdigit()):
            resultado["termino_corto"] = bool(termino)
            return resultado

        resultado["tickets"] = ServicioBusqueda._tickets(usuario, termino, limite)
        resultado["articulos"] = ServicioBusqueda._articulos(usuario, termino, limite)
        resultado["usuarios"] = ServicioBusqueda._usuarios(usuario, termino, limite)
        resultado["total"] = (
            len(resultado["tickets"]) + len(resultado["articulos"]) + len(resultado["usuarios"])
        )
        return resultado

    @staticmethod
    def _patron(termino):
        # El escape evita que un % o un _ escritos por el usuario se
        # interpreten como comodines y traigan media base de datos.
        limpio = termino.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{limpio}%"

    @staticmethod
    def _tickets(usuario, termino, limite):
        """Tickets por numero exacto o por texto, ya filtrados por permiso.

        Se piden mas filas de las que se devuelven porque el filtro de permiso
        se aplica en Python: pedir justo el limite dejaria listas cortas en
        cuanto una sola fila no fuera visible.
        """
        condiciones = [Ticket.texto.ilike(ServicioBusqueda._patron(termino), escape="\\")]

        posible_id = termino.lstrip("#").strip()
        if posible_id.isdigit():
            condiciones.append(Ticket.id == int(posible_id))

        candidatos = db.session.execute(
            select(Ticket).where(or_(*condiciones)).order_by(Ticket.id.desc()).limit(limite * 5)
        ).scalars().all()

        visibles = []
        for ticket in candidatos:
            if ServicioPermisos.puede_ver_ticket(usuario, ticket):
                visibles.append(ticket)
            if len(visibles) >= limite:
                break
        return visibles

    @staticmethod
    def _articulos(usuario, termino, limite):
        patron = ServicioBusqueda._patron(termino)
        query = select(Articulo).where(
            or_(
                Articulo.titulo.ilike(patron, escape="\\"),
                Articulo.resumen.ilike(patron, escape="\\"),
                Articulo.contenido.ilike(patron, escape="\\"),
                Articulo.etiquetas.ilike(patron, escape="\\"),
            )
        )
        if not ServicioPermisos.es_personal(usuario):
            query = query.where(Articulo.publicado.is_(True))

        return db.session.execute(
            query.order_by(Articulo.vistas.desc(), Articulo.id.desc()).limit(limite)
        ).scalars().all()

    @staticmethod
    def _usuarios(usuario, termino, limite):
        if usuario.rol != RolUsuario.ADMIN:
            return []
        patron = ServicioBusqueda._patron(termino)
        return db.session.execute(
            select(Usuario)
            .where(or_(Usuario.nombre.ilike(patron, escape="\\"), Usuario.email.ilike(patron, escape="\\")))
            .order_by(Usuario.nombre)
            .limit(limite)
        ).scalars().all()
