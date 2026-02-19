"""
Preparacao do dataset de treino para o modelo Wings.

Fluxo:
  1. Busca features computadas (features_pacote) do banco
  2. Join com maliciosos_conhecidos para labels (1=malicioso, 0=legitimo)
  3. Aplica SMOTE para balanceamento de classes
  4. Salva X_train, X_test, y_train, y_test em .parquet
  5. Gera relatorio de analise exploratoria

Criterios de label:
  - 1 (malicioso): presente em maliciosos_conhecidos
  - 0 (legitimo): idade > 180 dias, github_stars > 100, mantenedores > 1
  - Descartado: zona cinza (nao se encaixa em nenhum criterio)
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sqlalchemy import select, exists

from specter.config import config
from specter.modelos.base import obter_sessao
from specter.modelos.features import FeaturePacote
from specter.modelos.maliciosos import MaliciosoConhecido
from specter.utils.logging_config import obter_logger

log = obter_logger("prepare_training_data")

COLUNAS_FEATURES = [
    "idade_dias",
    "dias_desde_ultima_publicacao",
    "total_versoes",
    "frequencia_versoes",
    "pacote_novo",
    "contagem_mantenedores",
    "mantenedor_unico",
    "tem_github",
    "estrelas_github",
    "idade_github_dias",
    "contribuidores_github",
    "tem_script_postinstall",
    "tem_script_preinstall",
    "tamanho_script_instalacao",
    "score_typosquatting",
    "distancia_edicao_minima",
    "provavel_typosquat",
]


def preparar_dataset(dir_saida: Path | None = None) -> dict:
    """
    Gera o dataset de treino completo.

    Retorna dict com estatisticas do dataset.
    Salva artefatos em dir_saida (default: data/).
    """
    dir_saida = dir_saida or config.DIR_DADOS
    dir_saida.mkdir(parents=True, exist_ok=True)

    sessao = obter_sessao()
    try:
        # 1. Buscar todos os features
        features_rows = sessao.execute(select(FeaturePacote)).scalars().all()

        if not features_rows:
            log.warning("dataset_vazio")
            return {"erro": "sem features computadas no banco"}

        # 2. IDs de pacotes maliciosos
        ids_maliciosos = set(
            sessao.execute(
                select(MaliciosoConhecido.pacote_id).distinct()
            ).scalars().all()
        )

        # 3. Construir DataFrame
        registros = []
        for f in features_rows:
            row = {col: getattr(f, col, None) for col in COLUNAS_FEATURES}
            row["pacote_id"] = f.pacote_id

            if f.pacote_id in ids_maliciosos:
                row["label"] = 1
            elif (
                (f.idade_dias or 0) > 180
                and (f.estrelas_github or 0) > 100
                and (f.contagem_mantenedores or 0) > 1
            ):
                row["label"] = 0
            else:
                row["label"] = None  # zona cinza

            registros.append(row)

        df = pd.DataFrame(registros)
        total_antes = len(df)

        # Remover zona cinza
        df = df.dropna(subset=["label"])
        df["label"] = df["label"].astype(int)

        # Preencher NaN nas features com 0
        for col in COLUNAS_FEATURES:
            df[col] = df[col].fillna(0)

        total_depois = len(df)
        n_maliciosos = int(df["label"].sum())
        n_legitimos = total_depois - n_maliciosos

        log.info(
            "dataset_construido",
            total_antes=total_antes,
            total_depois=total_depois,
            maliciosos=n_maliciosos,
            legitimos=n_legitimos,
        )

        if total_depois < 10:
            log.warning("dataset_muito_pequeno", total=total_depois)
            return {"erro": "dataset muito pequeno", "total": total_depois}

        # 4. Split train/test
        X = df[COLUNAS_FEATURES].values
        y = df["label"].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if n_maliciosos >= 2 else None
        )

        # 5. SMOTE para balanceamento
        if n_maliciosos >= 6:
            try:
                smote = SMOTE(random_state=42, k_neighbors=min(5, n_maliciosos - 1))
                X_train, y_train = smote.fit_resample(X_train, y_train)
                log.info(
                    "smote_aplicado",
                    train_size_antes=len(y) - len(y_test),
                    train_size_depois=len(y_train),
                )
            except Exception as e:
                log.warning("smote_falhou", erro=str(e))

        # 6. Salvar artefatos
        df_train = pd.DataFrame(X_train, columns=COLUNAS_FEATURES)
        df_train["label"] = y_train
        df_train.to_parquet(dir_saida / "train.parquet", index=False)

        df_test = pd.DataFrame(X_test, columns=COLUNAS_FEATURES)
        df_test["label"] = y_test
        df_test.to_parquet(dir_saida / "test.parquet", index=False)

        # features.json
        (dir_saida / "features.json").write_text(
            json.dumps(COLUNAS_FEATURES, indent=2), encoding="utf-8"
        )

        # Estatisticas
        stats = {
            "total_registros": total_antes,
            "total_com_label": total_depois,
            "maliciosos": n_maliciosos,
            "legitimos": n_legitimos,
            "ratio_maliciosos": round(n_maliciosos / max(total_depois, 1), 4),
            "train_size": len(y_train),
            "test_size": len(y_test),
            "features": COLUNAS_FEATURES,
            "gerado_em": datetime.utcnow().isoformat(),
        }

        (dir_saida / "dataset_stats.json").write_text(
            json.dumps(stats, indent=2), encoding="utf-8"
        )

        # 7. Relatorio
        _gerar_relatorio(df, COLUNAS_FEATURES, stats, dir_saida)

        log.info("dataset_salvo", diretorio=str(dir_saida))
        return stats

    finally:
        sessao.close()


def _gerar_relatorio(df: pd.DataFrame, features: list, stats: dict, dir_saida: Path):
    """Gera relatorio de analise exploratoria basico."""
    linhas = [
        "=" * 60,
        "SPECTER — Relatorio do Dataset de Treino",
        "=" * 60,
        "",
        f"Total de registros: {stats['total_registros']}",
        f"Com label definido: {stats['total_com_label']}",
        f"Maliciosos: {stats['maliciosos']} ({stats['ratio_maliciosos']*100:.1f}%)",
        f"Legitimos: {stats['legitimos']}",
        f"Treino: {stats['train_size']} | Teste: {stats['test_size']}",
        "",
        "-" * 60,
        "DISTRIBUICAO POR FEATURE (media por classe)",
        "-" * 60,
    ]

    for feat in features:
        media_mal = df[df["label"] == 1][feat].mean()
        media_leg = df[df["label"] == 0][feat].mean()
        linhas.append(f"  {feat:40s} | mal={media_mal:8.2f} | leg={media_leg:8.2f}")

    linhas.extend([
        "",
        "-" * 60,
        "CORRELACAO COM LABEL",
        "-" * 60,
    ])

    corr = df[features + ["label"]].corr()["label"].drop("label").sort_values(ascending=False)
    for feat, val in corr.items():
        linhas.append(f"  {feat:40s} | corr={val:+.4f}")

    (dir_saida / "dataset_report.txt").write_text(
        "\n".join(linhas), encoding="utf-8"
    )
