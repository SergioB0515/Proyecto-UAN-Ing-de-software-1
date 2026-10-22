import pytest

from app.extensions import db
from app.formato import markdown_seguro
from app.models.enum import Categoria, RolUsuario
from app.services.base_conocimiento import ServicioBaseConocimiento, terminos
from app.services.exceptions import ArticuloNoEncontradoError
from tests.fabricas import crear_usuario


@pytest.fixture
def autor():
    return crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)


def _articulo(autor, titulo, contenido, categoria=Categoria.REDES, etiquetas=None, publicado=True):
    return ServicioBaseConocimiento.crear(autor.id, titulo, contenido, categoria, etiquetas=etiquetas, publicado=publicado)


def test_validaciones(autor):
    with pytest.raises(ValueError):
        _articulo(autor, "abc", "contenido suficiente para la prueba")
    with pytest.raises(ValueError):
        _articulo(autor, "Título correcto", "corto")
    with pytest.raises(ValueError):
        ServicioBaseConocimiento.crear(autor.id, "Título correcto", "contenido suficiente para la prueba", "redes")


def test_etiquetas_se_normalizan(autor):
    a = _articulo(autor, "Etiquetas normalizadas", "contenido suficiente para la prueba", etiquetas=" VPN, vpn ,Remoto,, ")
    assert a.etiquetas == "vpn, remoto"
    assert a.lista_etiquetas == ["vpn", "remoto"]


def test_terminos_ignora_acentos_y_palabras_vacias():
    assert terminos("No puedo conectarme a la VPN") == {"conectarme", "vpn"}
    assert terminos("Contraseña") == terminos("contrasena")


def test_sugerir_prioriza_coincidencias_de_titulo(autor):
    vpn = _articulo(autor, "Conexión VPN zafiro corporativa", "Pasos para configurar el cliente zafiro en casa", etiquetas="vpn, zafiro")
    _articulo(autor, "Impresoras del piso zafiro", "Cómo vaciar la cola de impresión", categoria=Categoria.INFRAESTRUCTURA)
    resultado = ServicioBaseConocimiento.sugerir("la vpn zafiro se desconecta cada rato")
    assert resultado and resultado[0][0].id == vpn.id


def test_sugerir_no_devuelve_borradores(autor):
    borrador = _articulo(autor, "Borrador ultravioleta secreto", "contenido ultravioleta de la guía", publicado=False)
    ids = [a.id for a, _p in ServicioBaseConocimiento.sugerir("problema ultravioleta secreto")]
    assert borrador.id not in ids
    with pytest.raises(ArticuloNoEncontradoError):
        ServicioBaseConocimiento.obtener(borrador.id)
    assert ServicioBaseConocimiento.obtener(borrador.id, incluir_borradores=True).id == borrador.id


def test_sugerir_texto_vacio():
    assert ServicioBaseConocimiento.sugerir("   ") == []
    assert ServicioBaseConocimiento.sugerir("hola, ayuda por favor") == []


def test_listar_busqueda_y_respaldo_por_terminos(autor):
    a = _articulo(autor, "Guía cormorán para redes", "Explicación sobre el cormorán de red")
    assert a in ServicioBaseConocimiento.listar(busqueda="cormorán")
    assert a in ServicioBaseConocimiento.listar(busqueda="cormoran redes caidas")


def test_votar_y_cambiar_voto(autor):
    a = _articulo(autor, "Artículo para votar", "contenido suficiente para la prueba")
    lector = crear_usuario()
    ServicioBaseConocimiento.votar(a.id, lector.id, True)
    ServicioBaseConocimiento.votar(a.id, lector.id, True)
    db.session.refresh(a)
    assert (a.votos_utiles, a.votos_no_utiles) == (1, 0)
    ServicioBaseConocimiento.votar(a.id, lector.id, False)
    db.session.refresh(a)
    assert (a.votos_utiles, a.votos_no_utiles) == (0, 1)
    assert ServicioBaseConocimiento.voto_de(a.id, lector.id) is False
    assert a.utilidad == 0


def test_archivar_y_resolucion(autor):
    a = _articulo(autor, "Artículo archivable", "contenido suficiente para la prueba")
    ServicioBaseConocimiento.registrar_resolucion(a.id)
    db.session.refresh(a)
    assert a.resoluciones == 1
    ServicioBaseConocimiento.cambiar_publicacion(autor.id, a.id, False)
    assert a not in ServicioBaseConocimiento.listar()


def test_markdown_escapa_html():
    html = str(markdown_seguro("## Título\n<script>alert(1)</script>\n- **uno**\n- [x](javascript:alert(1))"))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<h4>Título</h4>" in html and "<strong>uno</strong>" in html
    assert 'href="javascript' not in html


def test_markdown_enlaces_y_codigo():
    html = str(markdown_seguro("Ver [guía](https://ejemplo.com/a) y `ping **x**`"))
    assert '<a href="https://ejemplo.com/a" rel="noopener noreferrer" target="_blank">guía</a>' in html
    assert "<code>ping **x**</code>" in html
