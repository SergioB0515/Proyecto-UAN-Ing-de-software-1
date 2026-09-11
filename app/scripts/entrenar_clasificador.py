
import json
import os
from datetime import datetime

import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

NOMBRE_MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

RUTA_DATASET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "dataset_tickets_final.csv")
RUTA_ARTIFACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_artifacts")
RUTA_CLASIFICADOR = os.path.join(RUTA_ARTIFACTS, "clasificador_embeddings.joblib")
RUTA_METADATA = os.path.join(RUTA_ARTIFACTS, "metadata.json")


def entrenar():
    print(f"Cargando dataset desde: {RUTA_DATASET}")
    df = pd.read_csv(RUTA_DATASET)
    print(f"{len(df)} tickets, {df['categoria'].nunique()} categorias")

    X_train, X_test, y_train, y_test = train_test_split(
        df["texto"], df["categoria"], test_size=0.2, random_state=42, stratify=df["categoria"]
    )

    print(f"\nDescargando/cargando modelo de embeddings '{NOMBRE_MODELO_EMBEDDINGS}'...")
    modelo_embeddings = SentenceTransformer(NOMBRE_MODELO_EMBEDDINGS)

    print("\n--- Fase 1: evaluacion honesta con datos de prueba nunca vistos ---")
    X_train_emb = modelo_embeddings.encode(X_train.tolist(), show_progress_bar=True)
    X_test_emb = modelo_embeddings.encode(X_test.tolist(), show_progress_bar=True)

    clasificador_evaluacion = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    clasificador_evaluacion.fit(X_train_emb, y_train)
    y_pred = clasificador_evaluacion.predict(X_test_emb)

    reporte = classification_report(y_test, y_pred, output_dict=True)
    print(classification_report(y_test, y_pred))
    exactitud = reporte["accuracy"]

    print("\n--- Fase 2: reentrenando con el dataset COMPLETO para el modelo final ---")
    X_todo_emb = modelo_embeddings.encode(df["texto"].tolist(), show_progress_bar=True)
    clasificador_final = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    clasificador_final.fit(X_todo_emb, df["categoria"])

    os.makedirs(RUTA_ARTIFACTS, exist_ok=True)
    joblib.dump(clasificador_final, RUTA_CLASIFICADOR)

    metadata = {
        "modelo_embeddings": NOMBRE_MODELO_EMBEDDINGS,
        "fecha_entrenamiento": datetime.now().isoformat(),
        "cantidad_tickets_entrenamiento": len(df),
        "categorias": sorted(df["categoria"].unique().tolist()),
        "exactitud_en_prueba": exactitud,
    }
    with open(RUTA_METADATA, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nModelo final guardado en: {RUTA_CLASIFICADOR}")
    print(f"Metadata guardada en: {RUTA_METADATA}")
    print(f"Exactitud de referencia (datos de prueba): {exactitud:.1%}")


if __name__ == "__main__":
    entrenar()