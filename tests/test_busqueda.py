"""Pruebas de la busqueda global.

El punto importante no es que encuentre, es que no devuelva nada que el usuario
no pueda abrir: un titulo visible en los resultados ya es informacion filtrada,
aunque el enlace diera 403.
"""

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.enum import Categoria, EstadoTicket, RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.base_conocimiento import ServicioBaseConocimiento
from app.services.busqueda import MIN_TERMINO, ServicioBusqueda
from app.services.seguimiento import ServicioSeguimiento
from tests.fabricas import crear_ticket, crear_usuario

AREA = Categoria.SEGURIDAD


@pytest.fixture
def admin():
    return crear_usuario(rol=RolUsuario.ADMIN)

@pytest.fixture(autouse=True)
def agentes_sin_rastro():
    """Desactiva al terminar los agentes creados en esta prueba.

    La base de pruebas se comparte entre archivos y se ejecutan en orden
    alfabetico: un agente de este archivo que quede activo y sin carga le
    cambia el resultado a las pruebas de sugerencia de agente que corren
    despues. Desactivarlo deja el area como estaba.
    """
    previos = {
        u.id for u in db.session.execute(
            select(Usuario).where(Usuario.rol == RolUsuario.AGENTE)
        ).scalars().all()
    }

    yield

    nuevos = db.session.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.AGENTE, Usuario.id.notin_(previos or {0})
        )
    ).scalars().all()
    for agente_creado in nuevos:
        agente_creado.activo = False
    db.session.commit()



@pytest.fixture
def agente():
    return crear_usuario(rol=RolUsuario.AGENTE, area=AREA)


@pytest.fixture
def marca():
    """Token unico por prueba: la base de pruebas es compartida y los nombres
    repetidos harian que el limite por grupo escondiera al usuario buscado."""
    return f"Buscable{uuid.uuid4().hex[:8]}"


@pytest.fixture
def duenio(marca):
    return crear_usuario(rol=RolUsuario.FINAL, nombre=f"Marta Quintero {marca}")


@pytest.fixture
def ajeno():
    return crear_usuario(rol=RolUsuario.FINAL)


@pytest.fixture
def ticket(duenio):
    return crear_ticket(duenio, categoria=AREA,
                        texto="el proyector de la sala omega no muestra imagen")


def _ids(resultado):
    return {t.id for t in resultado["tickets"]}


def test_un_termino_corto_no_busca(duenio):
    resultado = ServicioBusqueda.buscar(duenio, "a" * (MIN_TERMINO - 1))
    assert resultado["termino_corto"] is True
    assert resultado["total"] == 0


def test_el_termino_vacio_no_marca_error(duenio):
    resultado = ServicioBusqueda.buscar(duenio, "   ")
    assert resultado["termino_corto"] is False
    assert resultado["total"] == 0


def test_el_creador_encuentra_su_ticket_por_texto(duenio, ticket):
    assert ticket.id in _ids(ServicioBusqueda.buscar(duenio, "proyector"))


def test_se_encuentra_por_numero_de_ticket(duenio, ticket):
    assert ticket.id in _ids(ServicioBusqueda.buscar(duenio, f"#{ticket.id}"))
    assert ticket.id in _ids(ServicioBusqueda.buscar(duenio, str(ticket.id)))


def test_un_usuario_ajeno_no_ve_el_ticket(ajeno, ticket):
    assert ticket.id not in _ids(ServicioBusqueda.buscar(ajeno, "proyector"))


def test_el_agente_del_area_ve_el_ticket_y_el_de_otra_area_no(agente, ticket):
    otra_area = crear_usuario(rol=RolUsuario.AGENTE, area=Categoria.INFRAESTRUCTURA)

    assert ticket.id in _ids(ServicioBusqueda.buscar(agente, "proyector"))
    assert ticket.id not in _ids(ServicioBusqueda.buscar(otra_area, "proyector"))


def test_un_seguidor_ve_el_ticket_que_sigue(ticket, duenio):
    seguidor = crear_usuario(rol=RolUsuario.AGENTE, area=Categoria.INFRAESTRUCTURA)
    ServicioSeguimiento.seguir(ticket.id, seguidor)

    assert ticket.id in _ids(ServicioBusqueda.buscar(seguidor, "proyector"))


def test_el_administrador_ve_cualquier_ticket(admin, ticket):
    assert ticket.id in _ids(ServicioBusqueda.buscar(admin, "proyector"))


def test_los_comodines_no_se_interpretan(duenio, ticket):
    # Un % escrito por el usuario tiene que buscarse literalmente, no traer
    # todas las filas de la tabla.
    assert _ids(ServicioBusqueda.buscar(duenio, "%%")) == set()


def test_los_articulos_publicados_los_ve_cualquiera(agente, duenio):
    articulo = ServicioBaseConocimiento.crear(
        agente.id, "Reservar la sala omega", "Pasos para reservar la sala de juntas omega",
        AREA, etiquetas="salas",
    )

    titulos = {a.id for a in ServicioBusqueda.buscar(duenio, "omega")["articulos"]}
    assert articulo.id in titulos


def test_un_borrador_solo_lo_ve_el_personal(agente, duenio):
    borrador = ServicioBaseConocimiento.crear(
        agente.id, "Guía interna de proyectores", "Procedimiento interno todavía sin publicar",
        AREA, publicado=False,
    )

    del_usuario = {a.id for a in ServicioBusqueda.buscar(duenio, "proyectores")["articulos"]}
    del_agente = {a.id for a in ServicioBusqueda.buscar(agente, "proyectores")["articulos"]}

    assert borrador.id not in del_usuario
    assert borrador.id in del_agente


def test_solo_el_administrador_busca_usuarios(admin, agente, duenio, marca):
    por_admin = {u.id for u in ServicioBusqueda.buscar(admin, marca)["usuarios"]}

    assert duenio.id in por_admin
    assert ServicioBusqueda.buscar(agente, marca)["usuarios"] == []
    assert ServicioBusqueda.buscar(duenio, marca)["usuarios"] == []


def test_se_busca_por_correo(admin, duenio):
    por_correo = {u.id for u in ServicioBusqueda.buscar(admin, duenio.email)["usuarios"]}
    assert duenio.id in por_correo


def test_el_total_suma_los_tres_grupos(admin, agente, duenio, ticket):
    ServicioBaseConocimiento.crear(
        agente.id, "Proyector de la sala omega", "Qué hacer si el proyector no da imagen", AREA,
    )

    resultado = ServicioBusqueda.buscar(admin, "proyector")
    assert resultado["total"] == (
        len(resultado["tickets"]) + len(resultado["articulos"]) + len(resultado["usuarios"])
    )
    assert resultado["total"] >= 2


def test_se_respeta_el_limite_por_grupo(duenio):
    for i in range(6):
        crear_ticket(duenio, categoria=AREA, texto=f"incidencia repetida numero {i} con telefono")

    resultado = ServicioBusqueda.buscar(duenio, "telefono", limite=3)
    assert len(resultado["tickets"]) == 3
