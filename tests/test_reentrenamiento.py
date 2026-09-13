"""
Pruebas de app.services.reentrenamiento

PARTE 1 -- _construir_dataset_combinado (rapidas, sin modelo de embeddings,
solo DB real + pandas):
1. Sin tickets reales ni correcciones, el combinado es exactamente el
   dataset sintetico (mismo tamano).
2. Un ticket real CERRADO y ya confirmado (clasificacion_baja_confianza
   False) se agrega como fila extra.
3. Un ticket EN_PROGRESO no se agrega (no esta cerrado).
4. Un ticket CERRADO pero todavia en baja confianza (sin confirmar) no
   se agrega -- solo cuentan los ya confirmados.
5. Un ticket que aparece en CorreccionClasificacion NO se cuenta dos
   veces (una por ser "ticket real" y otra por la correccion) -- el que
   habria sido el bug de doble peso si no se excluye explicitamente.
6. Una correccion de un ticket ya BORRADO de la tabla tickets se sigue
   contando igual (el texto esta denormalizado en la propia correccion,
   no depende de un join contra tickets).

PARTE 2 -- reentrenar_si_mejora (requiere sentence-transformers real,
NO se corrio en este sandbox por espacio en disco -- ver nota al final
del archivo. Sergio debe correr estas manualmente antes de dar el punto
por cerrado):
7. Sin metadata.json previo, aborta sin tronar y sin tocar nada.
8. Caso real: corre contra el dataset combinado y compara exactitudes
   (no se puede forzar de forma determinista si mejora o empeora sin
   mockear sklearn, que va contra la regla de "DB real, no mocks" del
   proyecto -- por eso esta prueba solo confirma que CORRE sin excepciones
   y que deja metadata.json en un estado valido, no que gane o pierda).
"""
import os
import json
import shutil

import pytest

from app.extensions import db
from app.services.tickets import ServicioTickets
from app.services.autenticacion import ServicioAutenticacion
from app.services import reentrenamiento as re_
from app.models.usuario import Usuario
from app.models.correccion_clasificacion import CorreccionClasificacion
from app.models.enum import RolUsuario, NivelUsuario, EstadoTicket, Categoria


EMAIL_ADMIN = "prueba_reentrenamiento_admin@empresa.com"
EMAIL_NORMAL = "prueba_reentrenamiento_normal@empresa.com"
EMAIL_AGENTE = "prueba_reentrenamiento_agente@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_AGENTE):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Reentrenamiento",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Reentrenamiento", email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Reentrenamiento", email=EMAIL_AGENTE,
        contrasena="ClaveSegura123!", rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
        area_soporte=Categoria.PERMISOS,
    )


def _crear_ticket_cerrado_confirmado(creador, agente):
    """Ticket real, cerrado, SIN baja confianza -- el caso normal que
    deberia contar como dato de entrenamiento confiable."""
    ticket = ServicioTickets.crear_ticket(creador=creador, texto="no puedo entrar a mi correo")
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    ServicioTickets.cambiar_estado(ticket_id=ticket.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=agente.id)
    return ticket


# ---------------------------------------------------------------------------
# PARTE 1 -- _construir_dataset_combinado
# ---------------------------------------------------------------------------

def test_el_combinado_siempre_incluye_todo_el_dataset_sintetico():
    """No se compara el tamano exacto contra el CSV -- esta es una DB
    compartida por TODA la sesion de pytest (ver tests/conftest.py), y
    para cuando este archivo corre, otros ya crearon tickets reales
    cerrados. Comparar por igualdad exacta aqui es el mismo error de
    'conteo absoluto contra DB compartida' que ya esta documentado como
    gotcha del proyecto -- se verifica el subconjunto, no el total."""
    import pandas as pd
    df_sintetico = pd.read_csv(re_.RUTA_DATASET_REFERENCIA)

    df_combinado = re_._construir_dataset_combinado()

    textos_combinado = set(df_combinado["texto"])
    faltantes = set(df_sintetico["texto"]) - textos_combinado
    assert not faltantes, (
        f"el dataset sintetico completo deberia estar incluido en el combinado, "
        f"faltan {len(faltantes)} filas, ejemplo: {next(iter(faltantes), None)}"
    )


def test_ticket_real_cerrado_confirmado_se_agrega():
    import pandas as pd
    df_antes = re_._construir_dataset_combinado()

    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    _crear_ticket_cerrado_confirmado(normal, agente)

    df_despues = re_._construir_dataset_combinado()

    assert len(df_despues) == len(df_antes) + 1, (
        "un ticket real cerrado y confirmado deberia sumar exactamente una fila "
        f"al combinado -- antes {len(df_antes)}, despues {len(df_despues)}"
    )
    assert "no puedo entrar a mi correo" in df_despues["texto"].values


def test_ticket_en_progreso_no_se_agrega():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    df_antes = re_._construir_dataset_combinado()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto="ticket que se queda en progreso")
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )

    df_despues = re_._construir_dataset_combinado()
    assert len(df_despues) == len(df_antes), (
        "un ticket EN_PROGRESO (no cerrado) no deberia contarse como dato de entrenamiento"
    )


def test_ticket_cerrado_sin_confirmar_no_se_agrega():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    df_antes = re_._construir_dataset_combinado()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto="ticket todavia en baja confianza")
    ticket.estado = EstadoTicket.CERRADO
    ticket.clasificacion_baja_confianza = True
    db.session.add(ticket)
    db.session.commit()

    df_despues = re_._construir_dataset_combinado()
    assert len(df_despues) == len(df_antes), (
        "un ticket cerrado pero todavia SIN confirmar su clasificacion no deberia "
        "contarse -- solo los ya confirmados son datos confiables"
    )


def test_ticket_con_correccion_no_se_cuenta_dos_veces():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    df_antes = re_._construir_dataset_combinado()

    ticket = _crear_ticket_cerrado_confirmado(normal, agente)
    db.session.add(CorreccionClasificacion(
        ticket_id=ticket.id,
        texto=ticket.texto,
        categoria_original=Categoria.OTROS,
        categoria_correcta=ticket.categoria,
        actor_id=agente.id,
    ))
    db.session.commit()

    df_despues = re_._construir_dataset_combinado()

    assert len(df_despues) == len(df_antes) + 1, (
        "un ticket que aparece en correcciones_clasificacion NO deberia contarse "
        "dos veces (una como ticket real y otra como correccion) -- se esperaba "
        f"+1 fila, antes {len(df_antes)}, despues {len(df_despues)}"
    )


def test_correccion_de_ticket_ya_borrado_se_sigue_contando():
    """El texto de la correccion esta denormalizado -- no depende de que
    el ticket original siga existiendo en la tabla tickets."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_cerrado_confirmado(normal, agente)
    correccion = CorreccionClasificacion(
        ticket_id=ticket.id,
        texto=ticket.texto,
        categoria_original=Categoria.OTROS,
        categoria_correcta=ticket.categoria,
        actor_id=agente.id,
    )
    db.session.add(correccion)
    db.session.commit()

    ticket_id_borrado = ticket.id
    db.session.delete(ticket)
    db.session.commit()

    df = re_._construir_dataset_combinado()
    assert correccion.texto in df["texto"].values, (
        "el texto de una correccion debe seguir presente en el combinado aunque "
        "el ticket original ya no exista en la tabla tickets"
    )


# ---------------------------------------------------------------------------
# PARTE 2 -- reentrenar_si_mejora (requiere el modelo real de embeddings)
# ---------------------------------------------------------------------------

def test_sin_metadata_previo_aborta_sin_tronar():
    """No requiere el modelo de embeddings -- el chequeo de metadata.json
    ocurre ANTES de cargar nada pesado."""
    respaldo = re_.RUTA_METADATA + ".respaldo_test"
    existia = os.path.exists(re_.RUTA_METADATA)
    if existia:
        shutil.move(re_.RUTA_METADATA, respaldo)
    try:
        re_.reentrenar_si_mejora()  # no debe lanzar excepcion
    finally:
        if existia:
            shutil.move(respaldo, re_.RUTA_METADATA)



def test_reentrenar_corre_sin_excepciones_y_deja_metadata_valido():
    metadata_antes = None
    if os.path.exists(re_.RUTA_METADATA):
        with open(re_.RUTA_METADATA, "r", encoding="utf-8") as f:
            metadata_antes = json.load(f)

    re_.reentrenar_si_mejora()

    with open(re_.RUTA_METADATA, "r", encoding="utf-8") as f:
        metadata_despues = json.load(f)

    assert "exactitud_en_prueba" in metadata_despues
    assert 0.0 <= metadata_despues["exactitud_en_prueba"] <= 1.0