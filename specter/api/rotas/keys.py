"""
Rotas de gerenciamento de API keys.
  POST /v1/keys/create — cria nova key free (sem auth)
  GET  /v1/keys/usage  — retorna uso do mes (com auth)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from specter.modelos.base import obter_sessao
from specter.modelos.api_keys import ChaveAPI
from specter.api.auth import dependencia_api_key, gerar_chave, hash_chave
from specter.utils.logging_config import obter_logger

log = obter_logger("rota_keys")

router = APIRouter()


class RequestCriarChave(BaseModel):
    email: EmailStr


class ResponseCriarChave(BaseModel):
    api_key: str
    tier: str
    message: str


class ResponseUso(BaseModel):
    email: str
    tier: str
    requisicoes_mes: int
    limite_mes: int | None
    criado_em: str


@router.post("/create", response_model=ResponseCriarChave)
async def criar_chave(body: RequestCriarChave):
    """Cria uma nova API key free. Nao requer autenticacao."""
    sessao = obter_sessao()
    try:
        chave_texto = gerar_chave()
        h = hash_chave(chave_texto)

        nova_chave = ChaveAPI(
            hash_chave=h,
            email=body.email,
            tier="free",
        )
        sessao.add(nova_chave)
        sessao.commit()

        log.info("chave_criada", email=body.email, tier="free")

        return ResponseCriarChave(
            api_key=chave_texto,
            tier="free",
            message="Chave criada. Guarde em local seguro — nao sera exibida novamente.",
        )
    except Exception as e:
        sessao.rollback()
        log.error("criar_chave_erro", erro=str(e))
        raise HTTPException(status_code=500, detail="Erro ao criar chave")
    finally:
        sessao.close()


class RequestUpgrade(BaseModel):
    tier: str
    plan: str = "pro_monthly"


class ResponseUpgrade(BaseModel):
    tier: str
    message: str
    checkout_url: str | None = None


@router.post("/upgrade", response_model=ResponseUpgrade)
async def upgrade_tier(
    body: RequestUpgrade,
    chave: ChaveAPI = Depends(dependencia_api_key),
):
    """
    Upgrade de tier. Para Pro, redireciona ao Stripe Checkout.
    Enterprise = contato comercial.
    """
    if body.tier == "enterprise":
        return ResponseUpgrade(
            tier="enterprise",
            message="Entre em contato: sales@specter.dev",
            checkout_url=None,
        )

    if body.tier != "pro":
        raise HTTPException(
            status_code=400,
            detail="Tier invalido. Use 'pro' ou 'enterprise'.",
        )

    if chave.tier in ("pro", "enterprise"):
        return ResponseUpgrade(
            tier=chave.tier,
            message=f"Voce ja possui o plano {chave.tier}.",
            checkout_url=None,
        )

    from specter.api.rotas.stripe_billing import criar_checkout, RequestCheckout

    try:
        checkout_body = RequestCheckout(plan=body.plan)
        resultado = await criar_checkout(checkout_body, chave)
        return ResponseUpgrade(
            tier="pro",
            message="Redirecionando para pagamento...",
            checkout_url=resultado.checkout_url,
        )
    except HTTPException as e:
        if e.status_code == 503:
            sessao = obter_sessao()
            try:
                registro = sessao.get(ChaveAPI, chave.id)
                if registro:
                    registro.tier = body.tier
                    sessao.commit()
                    log.info("tier_upgrade_fallback", email=registro.email, novo_tier=body.tier)
                    return ResponseUpgrade(
                        tier=body.tier,
                        message=f"Tier atualizado para '{body.tier}' (Stripe offline, upgrade cortesia).",
                        checkout_url=None,
                    )
            except Exception:
                sessao.rollback()
            finally:
                sessao.close()
        raise


@router.get("/usage", response_model=ResponseUso)
async def obter_uso(chave: ChaveAPI = Depends(dependencia_api_key)):
    """Retorna uso do mes atual da API key."""
    limites = {"free": 500, "pro": None, "enterprise": None}

    return ResponseUso(
        email=chave.email,
        tier=chave.tier,
        requisicoes_mes=chave.requisicoes_mes,
        limite_mes=limites.get(chave.tier),
        criado_em=chave.criado_em.isoformat() if chave.criado_em else "",
    )
