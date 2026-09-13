"""
Pruebas de ServicioPalabraClave (v2.1 -- CRUD admin de palabras clave)

Que verifica:
1-2.   listar_palabras_clave: por default solo trae activas; con
       incluir_inactivas=True trae tambien las desactivadas.
3-5.   crear_palabra_clave: caso valido, normaliza texto (mayusculas /
       espacios) antes de comparar duplicados, duplicada real -> error.
6-9.   editar_palabra_clave: caso valido, no encontrada, NO se autobloquea
       al editar sin cambiar texto/categoria (regresion del bug real que
       encontramos: el chequeo de duplicado no excluia el propio id),
       duplicada real contra OTRA palabra existente.
10-11. desactivar_palabra_clave: caso valido (activa queda en False de
       verdad, no solo la comparacion == que no asigna nada -- otra
       regresion del bug real), no encontrada.
12-13. reactivar_palabra_clave: caso valido, duplicada si ya existe otra
       activa con el mismo texto+categoria mientras esta estaba inactiva.
14.    Integracion con el cache del clasificador: crear/desactivar una
       palabra clave debe invalidar _cache_palabras_clave de
       clasificacion_avanzada.py -- este es el bug real de "cambios en
       la DB que el clasificador nunca ve sin reiniciar el servidor"
       que encontramos en esta sesion.
"""
import pytest

from app.extensions import db
from app.services.palabra_clave import ServicioPalabraClave
from app.services import clasificacion_avanzada as ca
from app.services.exceptions import PalabraClaveDuplicadaError, PalabraClaveNoEncontradaError
from app.models.palabra_clave import PalabraClave
from app.models.enum import Categoria


@pytest.fixture(autouse=True)
def limpiar_palabras_clave():
    """Cada test arranca con la tabla vacia -- estas pruebas son sobre el
    CRUD en si, no sobre las palabras clave reales de produccion."""
    PalabraClave.query.delete()
    db.session.commit()
    ca.invalidar_cache_palabras_clave()
    yield
    PalabraClave.query.delete()
    db.session.commit()
    ca.invalidar_cache_palabras_clave()


def _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=1.0):
    return ServicioPalabraClave.crear_palabra_clave(texto, categoria, peso, actor_id=1)


# ---------------------------------------------------------------------------
# listar_palabras_clave
# ---------------------------------------------------------------------------

def test_listar_solo_trae_activas_por_default():
    activa = _crear(texto="no hay wifi")
    inactiva = _crear(texto="internet lento")
    ServicioPalabraClave.desactivar_palabra_clave(inactiva.id, actor_id=1)

    resultado = ServicioPalabraClave.listar_palabras_clave()
    ids = {p.id for p in resultado}

    assert activa.id in ids
    assert inactiva.id not in ids, "una palabra desactivada no deberia aparecer por default"


def test_listar_incluir_inactivas_las_trae_tambien():
    activa = _crear(texto="no hay wifi")
    inactiva = _crear(texto="internet lento")
    ServicioPalabraClave.desactivar_palabra_clave(inactiva.id, actor_id=1)

    resultado = ServicioPalabraClave.listar_palabras_clave(incluir_inactivas=True)
    ids = {p.id for p in resultado}

    assert activa.id in ids
    assert inactiva.id in ids, "con incluir_inactivas=True tambien deben aparecer las desactivadas"


# ---------------------------------------------------------------------------
# crear_palabra_clave
# ---------------------------------------------------------------------------

def test_crear_palabra_clave_valido():
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=2.0)
    assert palabra.texto == "no hay wifi"
    assert palabra.categoria == Categoria.REDES
    assert palabra.activa is True


def test_crear_normaliza_texto_antes_de_comparar_duplicado():
    _crear(texto="no hay wifi", categoria=Categoria.REDES)

    with pytest.raises(PalabraClaveDuplicadaError):
        # mismo texto con mayusculas y espacios de mas -- debe detectarse igual
        _crear(texto="  NO HAY WIFI  ", categoria=Categoria.REDES)


def test_crear_palabra_clave_duplicada():
    _crear(texto="no hay wifi", categoria=Categoria.REDES)
    with pytest.raises(PalabraClaveDuplicadaError):
        _crear(texto="no hay wifi", categoria=Categoria.REDES)


# ---------------------------------------------------------------------------
# editar_palabra_clave
# ---------------------------------------------------------------------------

def test_editar_palabra_clave_valido():
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=1.0)

    editada = ServicioPalabraClave.editar_palabra_clave(
        palabra.id, texto="no hay internet", categoria=Categoria.REDES, peso=2.5, actor_id=1,
    )

    assert editada.texto == "no hay internet"
    assert editada.peso == 2.5


def test_editar_palabra_clave_no_encontrada():
    with pytest.raises(PalabraClaveNoEncontradaError):
        ServicioPalabraClave.editar_palabra_clave(
            999999, texto="x", categoria=Categoria.REDES, peso=1.0, actor_id=1,
        )


def test_editar_sin_cambiar_texto_categoria_no_se_autobloquea():
    """Regresion: el chequeo de duplicado original no excluia el propio
    id, asi que guardar sin cambiar texto/categoria (solo el peso, por
    ejemplo) se detectaba a si misma como 'ya existe' y tronaba."""
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=1.0)

    editada = ServicioPalabraClave.editar_palabra_clave(
        palabra.id, texto="no hay wifi", categoria=Categoria.REDES, peso=3.0, actor_id=1,
    )

    assert editada.peso == 3.0, "deberia poder editar solo el peso sin autobloquearse por duplicado"


def test_editar_palabra_clave_duplicada_contra_otra():
    _crear(texto="no hay wifi", categoria=Categoria.REDES)
    otra = _crear(texto="internet lento", categoria=Categoria.REDES)

    with pytest.raises(PalabraClaveDuplicadaError):
        ServicioPalabraClave.editar_palabra_clave(
            otra.id, texto="no hay wifi", categoria=Categoria.REDES, peso=1.0, actor_id=1,
        )


# ---------------------------------------------------------------------------
# desactivar_palabra_clave / reactivar_palabra_clave
# ---------------------------------------------------------------------------

def test_desactivar_palabra_clave_valido():
    """Regresion: la version original hacia `palabra.activa == False`
    (comparacion, no asignacion) y no cambiaba nada en la DB."""
    palabra = _crear(texto="no hay wifi")

    ServicioPalabraClave.desactivar_palabra_clave(palabra.id, actor_id=1)

    db.session.refresh(palabra)
    assert palabra.activa is False, (
        "se esperaba que activa quedara en False de verdad tras desactivar"
    )


def test_desactivar_palabra_clave_no_encontrada():
    with pytest.raises(PalabraClaveNoEncontradaError):
        ServicioPalabraClave.desactivar_palabra_clave(999999, actor_id=1)


def test_reactivar_palabra_clave_valido():
    palabra = _crear(texto="no hay wifi")
    ServicioPalabraClave.desactivar_palabra_clave(palabra.id, actor_id=1)

    ServicioPalabraClave.reactivar_palabra_clave(palabra.id, actor_id=1)

    db.session.refresh(palabra)
    assert palabra.activa is True


def test_reactivar_bloquea_si_ya_hay_otra_activa_igual():
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES)
    ServicioPalabraClave.desactivar_palabra_clave(palabra.id, actor_id=1)

    # mientras estaba inactiva, se crea otra con el mismo texto+categoria
    _crear(texto="no hay wifi", categoria=Categoria.REDES)

    with pytest.raises(PalabraClaveDuplicadaError):
        ServicioPalabraClave.reactivar_palabra_clave(palabra.id, actor_id=1)


# ---------------------------------------------------------------------------
# Integracion con el cache del clasificador (el bug real de esta sesion)
# ---------------------------------------------------------------------------

def test_crear_invalida_el_cache_del_clasificador():
    # fuerza a que el cache quede poblado con el estado actual (vacio)
    ca._cargar_palabras_clave()
    assert ca._cache_palabras_clave == []

    _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=2.0)

    # sin llamar invalidar_cache_palabras_clave() de nuevo aqui -- el
    # SERVICIO debe haberlo hecho solo dentro de crear_palabra_clave()
    recargado = ca._cargar_palabras_clave()
    assert ("no hay wifi", "redes", 2.0) in recargado, (
        "el cache del clasificador deberia reflejar la palabra clave recien "
        "creada sin necesidad de reiniciar el servidor -- si esto falla, el "
        "servicio dejo de invalidar el cache tras el commit"
    )


def test_desactivar_invalida_el_cache_del_clasificador():
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=2.0)
    ca._cargar_palabras_clave()  # puebla el cache con la palabra activa

    ServicioPalabraClave.desactivar_palabra_clave(palabra.id, actor_id=1)

    recargado = ca._cargar_palabras_clave()
    assert ("no hay wifi", "redes", 2.0) not in recargado, (
        "el cache del clasificador no deberia seguir usando una palabra clave "
        "que se acaba de desactivar"
    )