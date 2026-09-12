"""
Pruebas de app.services.clasificacion_avanzada

PARTE 1 -- Capa 1 y Capa 2 (rapidas, sin modelo de embeddings):
1-4. _capa1_palabras_clave: deteccion, sin coincidencias, case-insensitive,
     normalizacion por el maximo cuando hay varias categorias con senal.
5-6. _capa2_casi_duplicado: casi-duplicado exacto contra el corpus real,
     texto sin parecido no dispara nada.

PARTE 2 -- Capa 3 y clasificar_ticket (LENTAS, cargan el modelo real de
sentence-transformers -- requieren conexion a internet la primera vez que
corren en esta maquina, para descargar/cachear el modelo de HuggingFace):
7. _capa3_modelo_ml: las probabilidades suman ~1.0.
8. _capa3_modelo_ml: un texto claro predice la categoria correcta.
9. clasificar_ticket con CLASIFICADOR_ML_ACTIVO=False -> usa el
   clasificador simple, baja_confianza siempre False.
10. clasificar_ticket con ML activo, texto claro -> alta confianza.
11. clasificar_ticket con ML activo, texto irreconocible -> OTROS +
    baja_confianza=True (el caso real "yo no poder ser" que encontramos
    en produccion, ahora como prueba de regresion).

Requisito de infraestructura para que esto corra en cualquier maquina:
dataset_tickets_final.csv debe existir en la raiz del proyecto -- Capa 2
lo lee en tiempo de ejecucion, no solo al entrenar.
"""
import pytest
from flask import current_app

from app.extensions import db
from app.models.palabra_clave import PalabraClave
from app.models.enum import Categoria
from app.services import clasificacion_avanzada as ca


@pytest.fixture(scope="module", autouse=True)
def palabras_clave_de_prueba():
    """Siembra un set de palabras clave controlado y determinista para
    estas pruebas -- no depende de las 91 reales que tengas sembradas en
    desarrollo, que podrian cambiar con el tiempo."""
    PalabraClave.query.delete()
    db.session.commit()

    db.session.add_all([
        PalabraClave(categoria=Categoria.REDES, texto="no hay wifi", peso=2.0, activa=True),
        PalabraClave(categoria=Categoria.INFRAESTRUCTURA, texto="no enciende", peso=2.0, activa=True),
        PalabraClave(categoria=Categoria.PERMISOS, texto="no tengo acceso a", peso=1.5, activa=True),
        PalabraClave(categoria=Categoria.CUENTAS_CONTRASENAS, texto="olvidé mi contraseña", peso=2.2, activa=True),
    ])
    db.session.commit()
    ca.invalidar_cache_palabras_clave()
    yield
    ca.invalidar_cache_palabras_clave()


@pytest.fixture(scope="module")
def con_clasificador_ml_activo():
    """Activa CLASIFICADOR_ML_ACTIVO y carga el modelo real UNA sola vez
    para todo este archivo -- y lo restaura al valor original al terminar,
    para no dejarlo prendido para otros archivos de test que corran
    despues en la misma sesion de pytest."""
    valor_original = current_app.config.get("CLASIFICADOR_ML_ACTIVO", False)
    current_app.config["CLASIFICADOR_ML_ACTIVO"] = True
    ca.inicializar()
    yield
    current_app.config["CLASIFICADOR_ML_ACTIVO"] = valor_original


# ---------------------------------------------------------------------------
# PARTE 1 -- Capa 1: palabras clave ponderadas
# ---------------------------------------------------------------------------

def test_capa1_detecta_palabra_clave():
    puntajes = ca._capa1_palabras_clave("no hay wifi en la oficina")
    assert puntajes["redes"] == 1.0, (
        f"se esperaba redes normalizado a 1.0 (unica categoria con senal), se obtuvo {puntajes}"
    )
    assert all(v == 0.0 for c, v in puntajes.items() if c != "redes"), (
        f"las demas categorias deberian quedar en 0, se obtuvo {puntajes}"
    )


def test_capa1_sin_coincidencias():
    puntajes = ca._capa1_palabras_clave("xyzabc texto sin ningun sentido 123")
    assert all(v == 0.0 for v in puntajes.values()), (
        f"sin ninguna palabra clave presente, se esperaban todos en 0, se obtuvo {puntajes}"
    )


def test_capa1_case_insensitive():
    puntajes = ca._capa1_palabras_clave("NO HAY WIFI EN LA OFICINA")
    assert puntajes["redes"] == 1.0, (
        f"la deteccion deberia ser insensible a mayusculas, se obtuvo {puntajes}"
    )


def test_capa1_normaliza_por_el_maximo_entre_categorias():
    # "no enciende" (infraestructura, peso 2.0) y "no tengo acceso a" (permisos, peso 1.5)
    texto = "no enciende el computador y ademas no tengo acceso a la vpn"
    puntajes = ca._capa1_palabras_clave(texto)
    assert puntajes["infraestructura"] == 1.0, (
        f"la de mayor peso (2.0) debe quedar normalizada a 1.0, se obtuvo {puntajes}"
    )
    assert abs(puntajes["permisos"] - 0.75) < 0.01, (
        f"permisos (peso 1.5) deberia quedar en proporcion 1.5/2.0=0.75, se obtuvo {puntajes['permisos']}"
    )


# ---------------------------------------------------------------------------
# PARTE 1 -- Capa 2: casi-duplicados vs. corpus de referencia
# ---------------------------------------------------------------------------

def test_capa2_detecta_casi_duplicado_exacto():
    corpus = ca._cargar_corpus_referencia()
    texto_referencia, categoria_referencia = corpus[0]

    puntajes = ca._capa2_casi_duplicado(texto_referencia)

    assert puntajes[categoria_referencia] == 1.0, (
        f"un texto identico a uno del corpus de referencia deberia dar 1.0 "
        f"en su propia categoria ({categoria_referencia}), se obtuvo {puntajes}"
    )


def test_capa2_texto_sin_parecido_no_dispara():
    puntajes = ca._capa2_casi_duplicado(
        "blaurgh znaxi ticket completamente inventado sin sentido alguno zzzqq wxyz"
    )
    assert all(v == 0.0 for v in puntajes.values()), (
        f"un texto sin parecido real a nada del corpus no deberia disparar ninguna categoria, "
        f"se obtuvo {puntajes}"
    )


# ---------------------------------------------------------------------------
# PARTE 2 -- Capa 3: modelo de embeddings (requiere el modelo cargado)
# ---------------------------------------------------------------------------

def test_capa3_probabilidades_suman_uno(con_clasificador_ml_activo):
    probs = ca._capa3_modelo_ml("no puedo entrar a la carpeta compartida de ventas")
    suma = sum(probs.values())
    assert abs(suma - 1.0) < 0.01, f"las probabilidades deberian sumar ~1.0, se obtuvo {suma}"


def test_capa3_texto_claro_predice_categoria_razonable(con_clasificador_ml_activo):
    # Nota: el modelo tiene 89.7% de exactitud, no 100% -- si esta prueba
    # llega a fallar alguna vez con un texto tan claro como este, es una
    # señal real de que algo se degrado (dataset, modelo, o el entrenamiento
    # se corrio distinto), no un test mal escrito.
    probs = ca._capa3_modelo_ml("no hay wifi en toda la oficina desde ayer")
    ganador = max(probs, key=probs.get)
    assert ganador == "redes", (
        f"se esperaba 'redes' como categoria ganadora para un texto claro de red, "
        f"se obtuvo '{ganador}' con probabilidades {probs}"
    )


# ---------------------------------------------------------------------------
# PARTE 2 -- clasificar_ticket: integracion completa + umbral
# ---------------------------------------------------------------------------

def test_clasificar_ticket_con_ml_desactivado_usa_clasificador_simple():
    valor_original = current_app.config.get("CLASIFICADOR_ML_ACTIVO", False)
    current_app.config["CLASIFICADOR_ML_ACTIVO"] = False
    try:
        _, baja_confianza = ca.clasificar_ticket("no hay wifi en la oficina")
        assert baja_confianza is False, (
            "con CLASIFICADOR_ML_ACTIVO=False, baja_confianza siempre debe ser False "
            "(el clasificador simple no tiene ese concepto)"
        )
    finally:
        current_app.config["CLASIFICADOR_ML_ACTIVO"] = valor_original


def test_clasificar_ticket_texto_claro_alta_confianza(con_clasificador_ml_activo):
    categoria, baja_confianza = ca.clasificar_ticket("no hay wifi en toda la oficina desde ayer")
    assert baja_confianza is False, (
        f"un texto claro no deberia caer en baja confianza, se obtuvo categoria={categoria}"
    )


def test_clasificar_ticket_texto_irreconocible_baja_confianza(con_clasificador_ml_activo):
    # Prueba de regresion del caso real que encontramos en produccion:
    # "yo no poder ser" -- el que revelo el bug de CLASIFICADOR_ML_ACTIVO
    # mal ubicado en config.py.
    categoria, baja_confianza = ca.clasificar_ticket("yo no poder ser")
    assert baja_confianza is True, (
        f"un texto irreconocible deberia caer en baja confianza, "
        f"se obtuvo categoria={categoria}, baja_confianza={baja_confianza}"
    )
    assert categoria == Categoria.OTROS, (
        f"cuando cae en baja confianza, la categoria asignada debe ser OTROS, se obtuvo {categoria}"
    )