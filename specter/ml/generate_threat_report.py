"""
Gerador de relatorio tecnico de ameacas do Specter.

Analisa o banco e produz:
  - Top 10 pacotes suspeitos detectados
  - Estatisticas gerais (distribuicao de risco)
  - Padroes encontrados (typosquatting, scripts, etc.)
  - Comparacao com OSV (exclusive detections)

Output:
  - threat_report.md (pronto para publicar)
  - threat_report_data.json (dados brutos)
"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, func, and_

from specter.config import config
from specter.modelos.base import obter_sessao
from specter.modelos.pacotes import Pacote
from specter.modelos.features import FeaturePacote
from specter.modelos.maliciosos import MaliciosoConhecido
from specter.utils.logging_config import obter_logger

log = obter_logger("threat_report")


def gerar_relatorio(dir_saida: Path | None = None) -> dict:
    """
    Gera o relatorio completo de ameacas.
    Retorna dict com todas as estatisticas.
    """
    dir_saida = dir_saida or config.RAIZ_PROJETO
    sessao = obter_sessao()

    try:
        # --- 1. Estatisticas gerais ---
        total_pacotes = sessao.execute(
            select(func.count(Pacote.id))
        ).scalar() or 0

        total_features = sessao.execute(
            select(func.count(FeaturePacote.id))
        ).scalar() or 0

        total_maliciosos_osv = sessao.execute(
            select(func.count(MaliciosoConhecido.id)).where(
                MaliciosoConhecido.fonte == "osv"
            )
        ).scalar() or 0

        risco_alto = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                FeaturePacote.score_risco > 0.7
            )
        ).scalar() or 0

        risco_medio = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                and_(FeaturePacote.score_risco >= 0.3, FeaturePacote.score_risco <= 0.7)
            )
        ).scalar() or 0

        risco_baixo = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                FeaturePacote.score_risco < 0.3
            )
        ).scalar() or 0

        # --- 2. Top 10 suspeitos ---
        top_suspeitos_rows = sessao.execute(
            select(FeaturePacote, Pacote)
            .join(Pacote, FeaturePacote.pacote_id == Pacote.id)
            .where(FeaturePacote.score_risco.isnot(None))
            .order_by(FeaturePacote.score_risco.desc())
            .limit(10)
        ).all()

        top_10 = []
        for feat, pkg in top_suspeitos_rows:
            eh_osv = sessao.execute(
                select(func.count(MaliciosoConhecido.id)).where(
                    MaliciosoConhecido.pacote_id == pkg.id
                )
            ).scalar() or 0

            top_10.append({
                "nome": pkg.nome,
                "ecossistema": pkg.ecossistema,
                "score_risco": feat.score_risco,
                "score_typosquatting": feat.score_typosquatting,
                "tem_postinstall": feat.tem_script_postinstall,
                "estrelas_github": feat.estrelas_github,
                "idade_dias": feat.idade_dias,
                "provavel_typosquat": feat.provavel_typosquat,
                "ja_conhecido_osv": eh_osv > 0,
            })

        # --- 3. Padroes ---
        typosquats = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                FeaturePacote.provavel_typosquat == True
            )
        ).scalar() or 0

        com_postinstall = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                FeaturePacote.tem_script_postinstall == True
            )
        ).scalar() or 0

        pacotes_novos = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                FeaturePacote.pacote_novo == True
            )
        ).scalar() or 0

        mantenedor_unico = sessao.execute(
            select(func.count(FeaturePacote.id)).where(
                FeaturePacote.mantenedor_unico == True
            )
        ).scalar() or 0

        # --- 4. Exclusive detections (nao no OSV) ---
        ids_maliciosos_osv = set(
            sessao.execute(
                select(MaliciosoConhecido.pacote_id).distinct()
            ).scalars().all()
        )

        exclusivos = 0
        for feat, pkg in top_suspeitos_rows:
            if feat.score_risco and feat.score_risco > 0.7:
                if pkg.id not in ids_maliciosos_osv:
                    exclusivos += 1

        stats = {
            "gerado_em": datetime.utcnow().isoformat(),
            "total_pacotes_analisados": total_pacotes,
            "total_com_features": total_features,
            "total_maliciosos_osv": total_maliciosos_osv,
            "risco_alto": risco_alto,
            "risco_medio": risco_medio,
            "risco_baixo": risco_baixo,
            "pct_risco_alto": round(risco_alto / max(total_features, 1) * 100, 2),
            "pct_risco_medio": round(risco_medio / max(total_features, 1) * 100, 2),
            "padroes": {
                "typosquats_detectados": typosquats,
                "com_postinstall_script": com_postinstall,
                "pacotes_novos_30d": pacotes_novos,
                "mantenedor_unico": mantenedor_unico,
            },
            "exclusive_detections": exclusivos,
            "top_10_suspeitos": top_10,
        }

        # --- Salvar JSON ---
        (dir_saida / "threat_report_data.json").write_text(
            json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # --- Gerar Markdown ---
        _gerar_markdown(stats, dir_saida)

        log.info("relatorio_gerado", exclusivos=exclusivos, total=total_pacotes)
        return stats

    finally:
        sessao.close()


def _gerar_markdown(stats: dict, dir_saida: Path):
    """Gera o relatorio em formato markdown."""
    linhas = [
        "# SPECTER — Relatorio de Ameacas em Supply Chain",
        "",
        f"**Gerado em:** {stats['gerado_em']}",
        "",
        "---",
        "",
        "## Resumo Executivo",
        "",
        f"- **{stats['total_pacotes_analisados']:,}** pacotes analisados",
        f"- **{stats['risco_alto']}** pacotes de risco alto ({stats['pct_risco_alto']}%)",
        f"- **{stats['risco_medio']}** pacotes em zona de revisao ({stats['pct_risco_medio']}%)",
        f"- **{stats['exclusive_detections']}** deteccoes exclusivas do Specter (nao presentes no OSV)",
        "",
        "---",
        "",
        "## Top 10 Pacotes Suspeitos",
        "",
        "| # | Pacote | Eco | Score | Typosquat | PostInstall | OSV? |",
        "|---|--------|-----|-------|-----------|-------------|------|",
    ]

    for i, pkg in enumerate(stats["top_10_suspeitos"], 1):
        osv = "Sim" if pkg["ja_conhecido_osv"] else "**NAO**"
        typo = f"{pkg['score_typosquatting']:.0f}%" if pkg["score_typosquatting"] else "N/A"
        post = "Sim" if pkg["tem_postinstall"] else "Nao"
        linhas.append(
            f"| {i} | {pkg['nome']} | {pkg['ecossistema']} | "
            f"{pkg['score_risco']:.2f} | {typo} | {post} | {osv} |"
        )

    linhas.extend([
        "",
        "---",
        "",
        "## Padroes Identificados",
        "",
        f"- **Typosquatting:** {stats['padroes']['typosquats_detectados']} pacotes detectados",
        f"- **PostInstall scripts:** {stats['padroes']['com_postinstall_script']} pacotes com scripts de instalacao",
        f"- **Pacotes novos (<30 dias):** {stats['padroes']['pacotes_novos_30d']}",
        f"- **Mantenedor unico:** {stats['padroes']['mantenedor_unico']} pacotes",
        "",
        "---",
        "",
        "## Metodologia",
        "",
        "O Specter combina analise estatistica (modelo Wings/XGBoost) com analise semantica (LLM) para detectar pacotes maliciosos em ecossistemas npm e PyPI.",
        "",
        "Features utilizadas: idade do pacote, frequencia de publicacao, typosquatting score (Levenshtein), presenca de install scripts, metricas GitHub, contagem de mantenedores.",
        "",
        "---",
        "",
        "*Specter — See what others can't.*",
    ])

    (dir_saida / "threat_report.md").write_text(
        "\n".join(linhas), encoding="utf-8"
    )
