import os
import json
from datetime import datetime

import joblib
import pandas as pd
from sqlalchemy import select
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from app.extensions import db
from app.models.ticket import Ticket
from app.models.correccion_clasificacion import CorreccionClasificacion
from app.models.enum import EstadoTicket
from app.services.clasificacion_avanzada import (
    RUTA_CLASIFICADOR,
    RUTA_DATASET_REFERENCIA,
    _cargar_modelo_embeddings,
    invalidar_cache_clasificador_ml,
)

NOMBRE_MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"
RUTA_ARTIFACTS = os.path.dirname(RUTA_CLASIFICADOR)
RUTA_METADATA = os.path.join(RUTA_ARTIFACTS, "metadata.json")
RUTA_CLASIFICADOR_TEMPORAL = os.path.join(RUTA_ARTIFACTS, "clasificador_embeddings.joblib.tmp")


def _construir_dataset_combinado():

    df_sintetico = pd.read_csv(RUTA_DATASET_REFERENCIA)
    filas = list(zip(df_sintetico["texto"], df_sintetico["categoria"]))

    ids_con_correccion = {
        fila[0] for fila in db.session.execute(select(CorreccionClasificacion.ticket_id)).all()
    }

    query_tickets = select(Ticket.texto, Ticket.categoria).where(
        Ticket.estado == EstadoTicket.CERRADO,
        Ticket.clasificacion_baja_confianza == False,
    )
    if ids_con_correccion:
        query_tickets = query_tickets.where(~Ticket.id.in_(ids_con_correccion))

    tickets_reales = db.session.execute(query_tickets).all()
    filas.extend((fila.texto, fila.categoria.value) for fila in tickets_reales)

    correcciones = db.session.execute(
        select(CorreccionClasificacion.texto, CorreccionClasificacion.categoria_correcta)
    ).all()
    filas.extend((fila.texto, fila.categoria_correcta.value) for fila in correcciones)

    return pd.DataFrame(filas, columns=["texto", "categoria"])


def reentrenar_si_mejora():

    if not os.path.exists(RUTA_METADATA):
        print("No hay metadata.json previo — no se puede comparar, se aborta el reentrenamiento.")
        return

    with open(RUTA_METADATA, "r", encoding="utf-8") as f:
        metadata_anterior = json.load(f)
    exactitud_anterior = metadata_anterior.get("exactitud_en_prueba", 0.0)

    df = _construir_dataset_combinado()
    if df["categoria"].nunique() < 2 or len(df) < 20:
        print("Dataset combinado insuficiente para reentrenar. Se aborta.")
        return

    X_train, X_test, y_train, y_test = train_test_split(
        df["texto"], df["categoria"], test_size=0.2, random_state=42, stratify=df["categoria"]
    )

    modelo_embeddings = _cargar_modelo_embeddings()
    X_train_emb = modelo_embeddings.encode(X_train.tolist())
    X_test_emb = modelo_embeddings.encode(X_test.tolist())

    candidato = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    candidato.fit(X_train_emb, y_train)
    exactitud_nueva = accuracy_score(y_test, candidato.predict(X_test_emb))

    print(f"Exactitud anterior: {exactitud_anterior:.1%} | Exactitud candidata: {exactitud_nueva:.1%}")

    if exactitud_nueva <= exactitud_anterior:
        print("El modelo candidato no mejora al de producción. No se reemplaza.")
        return

    X_todo_emb = modelo_embeddings.encode(df["texto"].tolist())
    modelo_final = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    modelo_final.fit(X_todo_emb, df["categoria"])


    joblib.dump(modelo_final, RUTA_CLASIFICADOR_TEMPORAL)
    os.replace(RUTA_CLASIFICADOR_TEMPORAL, RUTA_CLASIFICADOR)

    metadata_nueva = {
        "modelo_embeddings": NOMBRE_MODELO_EMBEDDINGS,
        "fecha_entrenamiento": datetime.now().isoformat(),
        "cantidad_tickets_entrenamiento": len(df),
        "categorias": sorted(df["categoria"].unique().tolist()),
        "exactitud_en_prueba": exactitud_nueva,
        "exactitud_anterior_reemplazada": exactitud_anterior,
    }
    with open(RUTA_METADATA, "w", encoding="utf-8") as f:
        json.dump(metadata_nueva, f, indent=2, ensure_ascii=False)

    invalidar_cache_clasificador_ml()
    print(f"Modelo reemplazado en producción. Nueva exactitud: {exactitud_nueva:.1%} (anterior: {exactitud_anterior:.1%})")