"""
Treinamento do modelo Wings — classificador de pacotes maliciosos.

Treina 3 modelos:
  1. XGBoostClassifier (principal) — com tuning Optuna
  2. RandomForestClassifier (ensemble secundario)
  3. LogisticRegression (baseline)

Metricas: Precision, Recall, F1, ROC-AUC, Confusion Matrix.
Foco em Recall alto (falso negativo e pior que falso positivo).

Artefatos salvos em models/:
  - wings_v1.joblib         (modelo treinado)
  - threshold.json          (threshold otimo)
  - training_report.txt     (relatorio completo)
  - feature_importance.json (ranking de features)
"""

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import optuna
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from xgboost import XGBClassifier

from specter.config import config
from specter.utils.logging_config import obter_logger

log = obter_logger("train_model")

optuna.logging.set_verbosity(optuna.logging.WARNING)


def _carregar_dados(dir_dados: Path) -> tuple:
    """Carrega datasets de treino/teste dos parquets."""
    features_path = dir_dados / "features.json"
    features = json.loads(features_path.read_text(encoding="utf-8"))

    train_df = pd.read_parquet(dir_dados / "train.parquet")
    test_df = pd.read_parquet(dir_dados / "test.parquet")

    X_train = train_df[features].values
    y_train = train_df["label"].values
    X_test = test_df[features].values
    y_test = test_df["label"].values

    return X_train, X_test, y_train, y_test, features


def _otimizar_xgboost(X_train, y_train, n_trials: int = 20) -> dict:
    """Hyperparameter tuning com Optuna para XGBoost."""

    scale_pos = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    def objetivo(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "scale_pos_weight": trial.suggest_float(
                "scale_pos_weight", scale_pos * 0.5, scale_pos * 2.0
            ),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 2.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 2.0),
            "use_label_encoder": False,
            "eval_metric": "logloss",
            "random_state": 42,
        }

        modelo = XGBClassifier(**params)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_train)
        return f1_score(y_train, y_pred)

    study = optuna.create_study(direction="maximize")
    study.optimize(objetivo, n_trials=n_trials, show_progress_bar=False)

    log.info(
        "optuna_completo",
        melhor_f1=round(study.best_value, 4),
        trials=n_trials,
    )
    return study.best_params


def _encontrar_threshold_otimo(y_true, y_proba) -> float:
    """Encontra threshold que maximiza F1."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
    idx = np.argmax(f1_scores)
    return float(thresholds[idx]) if idx < len(thresholds) else 0.5


def _calcular_feature_importance_shap(modelo, X_test, features: list) -> dict:
    """Calcula feature importance usando SHAP."""
    try:
        explainer = shap.TreeExplainer(modelo)
        shap_values = explainer.shap_values(X_test[:min(200, len(X_test))])

        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        importancias = np.abs(shap_values).mean(axis=0)
        ranking = sorted(
            zip(features, importancias.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return {nome: round(val, 6) for nome, val in ranking}
    except Exception as e:
        log.warning("shap_erro", erro=str(e))
        if hasattr(modelo, "feature_importances_"):
            ranking = sorted(
                zip(features, modelo.feature_importances_.tolist()),
                key=lambda x: x[1],
                reverse=True,
            )
            return {nome: round(val, 6) for nome, val in ranking}
        return {}


def predict(features_dict: dict, dir_modelos: Path | None = None) -> dict:
    """
    Predicao de risco para um pacote.

    Retorna:
      {"score": float, "top_reasons": list[str], "verdict": str}
    """
    dir_modelos = dir_modelos or config.DIR_MODELOS

    modelo = joblib.load(dir_modelos / "wings_v1.joblib")
    threshold_data = json.loads(
        (dir_modelos / "threshold.json").read_text(encoding="utf-8")
    )
    feature_names = json.loads(
        (config.DIR_DADOS / "features.json").read_text(encoding="utf-8")
    )
    importance = json.loads(
        (dir_modelos / "feature_importance.json").read_text(encoding="utf-8")
    )

    X = np.array([[features_dict.get(f, 0) for f in feature_names]])
    proba = modelo.predict_proba(X)[0][1]
    threshold = threshold_data["threshold"]

    score = float(round(proba, 4))

    top_reasons = []
    sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    for feat_nome, _ in sorted_features[:3]:
        valor = features_dict.get(feat_nome, 0)
        if valor:
            top_reasons.append(f"{feat_nome}={valor}")

    if score >= 0.7:
        verdict = "blocked"
    elif score >= threshold:
        verdict = "review"
    else:
        verdict = "safe"

    return {
        "score": score,
        "verdict": verdict,
        "top_reasons": top_reasons,
        "threshold": threshold,
    }


def treinar(
    dir_dados: Path | None = None,
    dir_modelos: Path | None = None,
    n_trials_optuna: int = 20,
) -> dict:
    """
    Pipeline completo de treinamento.
    Retorna dict com metricas de todos os modelos.
    """
    dir_dados = dir_dados or config.DIR_DADOS
    dir_modelos = dir_modelos or config.DIR_MODELOS
    dir_modelos.mkdir(parents=True, exist_ok=True)

    X_train, X_test, y_train, y_test, features = _carregar_dados(dir_dados)

    log.info(
        "treino_iniciado",
        train=len(y_train),
        test=len(y_test),
        features=len(features),
    )

    # --- 1. XGBoost com Optuna ---
    log.info("treinando_xgboost_optuna")
    best_params = _otimizar_xgboost(X_train, y_train, n_trials=n_trials_optuna)
    best_params.update({"use_label_encoder": False, "eval_metric": "logloss", "random_state": 42})
    xgb = XGBClassifier(**best_params)
    xgb.fit(X_train, y_train)

    # --- 2. RandomForest ---
    log.info("treinando_random_forest")
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)

    # --- 3. LogisticRegression (baseline) ---
    log.info("treinando_logistic_regression")
    lr = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
    )
    lr.fit(X_train, y_train)

    # --- Avaliar todos ---
    resultados = {}
    for nome_modelo, modelo in [("xgboost", xgb), ("random_forest", rf), ("logistic_regression", lr)]:
        y_pred = modelo.predict(X_test)
        y_proba = modelo.predict_proba(X_test)[:, 1]

        resultados[nome_modelo] = {
            "classification_report": classification_report(y_test, y_pred, output_dict=True),
            "roc_auc": float(round(roc_auc_score(y_test, y_proba), 4)),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "f1": float(round(f1_score(y_test, y_pred), 4)),
        }

        log.info(
            f"resultado_{nome_modelo}",
            f1=resultados[nome_modelo]["f1"],
            roc_auc=resultados[nome_modelo]["roc_auc"],
        )

    # --- Salvar melhor modelo (XGBoost) ---
    y_proba_xgb = xgb.predict_proba(X_test)[:, 1]
    threshold = _encontrar_threshold_otimo(y_test, y_proba_xgb)

    joblib.dump(xgb, dir_modelos / "wings_v1.joblib")
    (dir_modelos / "threshold.json").write_text(
        json.dumps({"threshold": round(threshold, 4), "gerado_em": datetime.utcnow().isoformat()}),
        encoding="utf-8",
    )

    # Feature importance via SHAP
    importance = _calcular_feature_importance_shap(xgb, X_test, features)
    (dir_modelos / "feature_importance.json").write_text(
        json.dumps(importance, indent=2), encoding="utf-8"
    )

    # Relatorio
    _gerar_relatorio_treino(resultados, threshold, importance, features, dir_modelos)

    log.info("treino_completo", modelo_salvo=str(dir_modelos / "wings_v1.joblib"))

    return {
        "melhor_modelo": "xgboost",
        "threshold": threshold,
        "resultados": resultados,
        "feature_importance": importance,
    }


def _gerar_relatorio_treino(
    resultados: dict, threshold: float, importance: dict, features: list, dir_modelos: Path
):
    """Gera relatorio de treino completo em texto."""
    linhas = [
        "=" * 70,
        "SPECTER WINGS — Relatorio de Treinamento",
        f"Gerado em: {datetime.utcnow().isoformat()}",
        "=" * 70,
        "",
    ]

    for nome, res in resultados.items():
        linhas.extend([
            f"--- {nome.upper()} ---",
            f"  F1-Score:  {res['f1']}",
            f"  ROC-AUC:   {res['roc_auc']}",
            f"  Confusion: {res['confusion_matrix']}",
            "",
        ])

    linhas.extend([
        f"Threshold otimo: {threshold:.4f}",
        "",
        "--- FEATURE IMPORTANCE (SHAP) ---",
    ])

    for feat, val in importance.items():
        linhas.append(f"  {feat:40s} | {val:.6f}")

    (dir_modelos / "training_report.txt").write_text(
        "\n".join(linhas), encoding="utf-8"
    )
