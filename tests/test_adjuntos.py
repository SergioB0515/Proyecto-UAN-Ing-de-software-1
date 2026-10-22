import io
import os

import pytest
from werkzeug.datastructures import FileStorage

from app.models.enum import RolUsuario
from app.services.adjuntos import ServicioAdjuntos, MAX_ADJUNTOS_POR_TICKET, TAMANO_MAXIMO_BYTES
from app.services.exceptions import AdjuntoInvalidoError, PermisoDenegadoError
from tests.fabricas import crear_ticket, crear_usuario

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def archivo(nombre, datos):
    return FileStorage(stream=io.BytesIO(datos), filename=nombre)


@pytest.fixture
def ticket():
    return crear_ticket(crear_usuario())


def test_guarda_archivo_valido_fuera_de_static(ticket):
    adjunto = ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("captura error.PNG", PNG))
    ruta = ServicioAdjuntos.ruta(adjunto)
    assert os.path.exists(ruta) and "static" not in ruta
    assert adjunto.nombre_original == "captura error.PNG"
    assert adjunto.nombre_guardado.endswith(".png") and adjunto.nombre_guardado != adjunto.nombre_original
    assert adjunto.tipo_mime == "image/png" and adjunto.es_imagen


@pytest.mark.parametrize("nombre", ["script.exe", "pagina.html", "imagen.svg", "sin_extension"])
def test_rechaza_extensiones_no_permitidas(ticket, nombre):
    with pytest.raises(AdjuntoInvalidoError):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo(nombre, b"contenido"))


def test_rechaza_contenido_que_no_coincide_con_extension(ticket):
    with pytest.raises(AdjuntoInvalidoError):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("falso.png", b"<html>no soy png</html>"))
    with pytest.raises(AdjuntoInvalidoError):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("binario.txt", b"MZ\x00\x00\x00"))


def test_rechaza_vacio_y_demasiado_grande(ticket):
    with pytest.raises(AdjuntoInvalidoError):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("vacio.txt", b""))
    with pytest.raises(AdjuntoInvalidoError):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("enorme.txt", b"a" * (TAMANO_MAXIMO_BYTES + 1)))


def test_limite_por_ticket(ticket):
    for i in range(MAX_ADJUNTOS_POR_TICKET):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo(f"log{i}.txt", b"linea de log"))
    with pytest.raises(AdjuntoInvalidoError):
        ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("uno_mas.txt", b"linea"))


def test_solo_autor_o_admin_elimina(ticket):
    adjunto = ServicioAdjuntos.guardar(ticket.id, ticket.creador_id, archivo("nota.txt", b"texto"))
    ruta = ServicioAdjuntos.ruta(adjunto)
    with pytest.raises(PermisoDenegadoError):
        ServicioAdjuntos.eliminar(adjunto.id, crear_usuario().id)
    ServicioAdjuntos.eliminar(adjunto.id, crear_usuario(RolUsuario.ADMIN).id)
    assert not os.path.exists(ruta)
    assert ServicioAdjuntos.listar(ticket.id) == []
