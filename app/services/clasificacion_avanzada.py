
import difflib
import os

import joblib
import pandas as pd
from flask import current_app

from app.extensions import db
from app.models.palabra_clave import PalabraClave
from app.models.enum import Categoria

RUTA_ARTIFACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_artifacts")
RUTA_CLASIFICADOR = os.path.join(RUTA_ARTIFACTS, "clasificador_embeddings.joblib")
RUTA_DATASET_REFERENCIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "dataset_tickets_final.csv")

UMBRAL_SIMILITUD_CASI_DUPLICADO = 0.85
UMBRAL_CONFIANZA_CLASIFICACION = 0.69

_modelo_embeddings = None
_clasificador_ml = None
_corpus_referencia = None
_cache_palabras_clave = None


def _cargar_modelo_embeddings():
    global _modelo_embeddings
    if _modelo_embeddings is None:
        from sentence_transformers import SentenceTransformer
        _modelo_embeddings = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _modelo_embeddings


def _cargar_clasificador_ml():
    global _clasificador_ml
    if _clasificador_ml is None:
        _clasificador_ml = joblib.load(RUTA_CLASIFICADOR)
    return _clasificador_ml


def _cargar_corpus_referencia():
    global _corpus_referencia
    if _corpus_referencia is None:
        df = pd.read_csv(RUTA_DATASET_REFERENCIA)
        _corpus_referencia = list(zip(df["texto"], df["categoria"]))
    return _corpus_referencia


def _cargar_palabras_clave():
    global _cache_palabras_clave
    if _cache_palabras_clave is None:
        filas = PalabraClave.query.filter_by(activa=True).all()
        _cache_palabras_clave = [(p.texto.lower(), p.categoria.value, p.peso) for p in filas]
    return _cache_palabras_clave


def invalidar_cache_palabras_clave():

    global _cache_palabras_clave
    _cache_palabras_clave = None


def inicializar():

    _cargar_modelo_embeddings()
    _cargar_clasificador_ml()
    _cargar_corpus_referencia()


def _capa1_palabras_clave(texto):
    texto_norm = texto.lower()
    categorias = [c.value for c in Categoria]
    puntajes = {c: 0.0 for c in categorias}
    for palabra, categoria, peso in _cargar_palabras_clave():
        if palabra in texto_norm:
            puntajes[categoria] += peso
    maximo = max(puntajes.values())
    if maximo > 0:
        puntajes = {c: v / maximo for c, v in puntajes.items()}
    return puntajes


def _capa2_casi_duplicado(texto):
    categorias = [c.value for c in Categoria]
    puntajes = {c: 0.0 for c in categorias}
    texto_norm = texto.lower()
    mejor_ratio, mejor_categoria = 0.0, None
    for texto_ref, categoria_ref in _cargar_corpus_referencia():
        r = difflib.SequenceMatcher(None, texto_norm, texto_ref.lower()).ratio()
        if r > mejor_ratio:
            mejor_ratio, mejor_categoria = r, categoria_ref
    if mejor_ratio > UMBRAL_SIMILITUD_CASI_DUPLICADO:
        puntajes[mejor_categoria] = 1.0
    return puntajes


def _capa3_modelo_ml(texto):
    modelo = _cargar_modelo_embeddings()
    clasificador = _cargar_clasificador_ml()
    embedding = modelo.encode([texto])
    probabilidades = clasificador.predict_proba(embedding)[0]
    return dict(zip(clasificador.classes_, probabilidades))


def clasificar_ticket(texto):

    if not current_app.config.get("CLASIFICADOR_ML_ACTIVO", False):
        from app.services.clasificador import ClasificadorTickets
        return ClasificadorTickets.clasificar(texto), False

    p1 = _capa1_palabras_clave(texto)
    p2 = _capa2_casi_duplicado(texto)
    p3 = _capa3_modelo_ml(texto)

    categorias = [c.value for c in Categoria]
    combinado = {c: p1.get(c, 0.0) + p2.get(c, 0.0) + p3.get(c, 0.0) for c in categorias}

    categoria_ganadora = max(combinado, key=combinado.get)
    puntaje_ganador = combinado[categoria_ganadora]

    if puntaje_ganador < UMBRAL_CONFIANZA_CLASIFICACION:
        return Categoria.OTROS, True

    return Categoria(categoria_ganadora), False