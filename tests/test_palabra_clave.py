import pytest

from app.extensions import db
from app.services.palabra_clave import ServicioPalabraClave
from app.services import clasificacion_avanzada as ca
from app.services.exceptions import PalabraClaveDuplicadaError, PalabraClaveNoEncontradaError
from app.models.palabra_clave import PalabraClave
from app.models.enum import Categoria


@pytest.fixture(autouse=True)
def limpiar_palabras_clave():
    PalabraClave.query.delete()
    db.session.commit()
    ca.invalidar_cache_palabras_clave()
    yield
    PalabraClave.query.delete()
    db.session.commit()
    ca.invalidar_cache_palabras_clave()


def _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=1.0):
    return ServicioPalabraClave.crear_palabra_clave(texto, categoria, peso, actor_id=1)


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


def test_crear_palabra_clave_valido():
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=2.0)
    assert palabra.texto == "no hay wifi"
    assert palabra.categoria == Categoria.REDES
    assert palabra.activa is True


def test_crear_normaliza_texto_antes_de_comparar_duplicado():
    _crear(texto="no hay wifi", categoria=Categoria.REDES)

    with pytest.raises(PalabraClaveDuplicadaError):
        _crear(texto="  NO HAY WIFI  ", categoria=Categoria.REDES)


def test_crear_palabra_clave_duplicada():
    _crear(texto="no hay wifi", categoria=Categoria.REDES)
    with pytest.raises(PalabraClaveDuplicadaError):
        _crear(texto="no hay wifi", categoria=Categoria.REDES)


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


def test_desactivar_palabra_clave_valido():
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

    _crear(texto="no hay wifi", categoria=Categoria.REDES)

    with pytest.raises(PalabraClaveDuplicadaError):
        ServicioPalabraClave.reactivar_palabra_clave(palabra.id, actor_id=1)


def test_crear_invalida_el_cache_del_clasificador():
    ca._cargar_palabras_clave()
    assert ca._cache_palabras_clave == []

    _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=2.0)

    recargado = ca._cargar_palabras_clave()
    assert ("no hay wifi", "redes", 2.0) in recargado, (
        "el cache del clasificador deberia reflejar la palabra clave recien "
        "creada sin necesidad de reiniciar el servidor -- si esto falla, el "
        "servicio dejo de invalidar el cache tras el commit"
    )


def test_desactivar_invalida_el_cache_del_clasificador():
    palabra = _crear(texto="no hay wifi", categoria=Categoria.REDES, peso=2.0)
    ca._cargar_palabras_clave()

    ServicioPalabraClave.desactivar_palabra_clave(palabra.id, actor_id=1)

    recargado = ca._cargar_palabras_clave()
    assert ("no hay wifi", "redes", 2.0) not in recargado, (
        "el cache del clasificador no deberia seguir usando una palabra clave "
        "que se acaba de desactivar"
    )