"""
Rotas de billing com Stripe.
  POST /v1/stripe/checkout  — cria sessao de checkout Stripe
  POST /v1/stripe/webhook   — recebe eventos do Stripe (assinatura criada/cancelada)
  GET  /v1/stripe/portal    — redireciona para o portal de gerenciamento Stripe
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from specter.config import config
from specter.modelos.base import obter_sessao
from specter.modelos.api_keys import ChaveAPI
from specter.api.auth import dependencia_api_key
from specter.utils.logging_config import obter_logger

log = obter_logger("stripe_billing")

router = APIRouter()

stripe.api_key = config.STRIPE_SECRET_KEY

_PRICE_MAP = {
    "pro_monthly": config.STRIPE_PRICE_PRO_MONTHLY,
    "pro_yearly": config.STRIPE_PRICE_PRO_YEARLY,
}

_TIER_POR_PRICE: dict[str, str] = {}


def _construir_tier_map() -> None:
    """Constroi mapa reverso price_id -> tier na inicializacao."""
    if config.STRIPE_PRICE_PRO_MONTHLY:
        _TIER_POR_PRICE[config.STRIPE_PRICE_PRO_MONTHLY] = "pro"
    if config.STRIPE_PRICE_PRO_YEARLY:
        _TIER_POR_PRICE[config.STRIPE_PRICE_PRO_YEARLY] = "pro"


_construir_tier_map()


def _obter_ou_criar_customer(chave: ChaveAPI) -> str:
    """Retorna stripe_customer_id existente ou cria um novo."""
    if chave.stripe_customer_id:
        return chave.stripe_customer_id

    customer = stripe.Customer.create(
        email=chave.email,
        metadata={"specter_key_id": str(chave.id)},
    )

    sessao = obter_sessao()
    try:
        registro = sessao.get(ChaveAPI, chave.id)
        if registro:
            registro.stripe_customer_id = customer.id
            sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()

    return customer.id


class RequestCheckout(BaseModel):
    plan: str = "pro_monthly"


class ResponseCheckout(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/checkout", response_model=ResponseCheckout)
async def criar_checkout(
    body: RequestCheckout,
    chave: ChaveAPI = Depends(dependencia_api_key),
):
    """Cria uma sessao Stripe Checkout para upgrade Pro."""
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe nao configurado. Defina STRIPE_SECRET_KEY no .env",
        )

    price_id = _PRICE_MAP.get(body.plan)
    if not price_id or price_id.startswith("price_COLOQUE"):
        raise HTTPException(
            status_code=400,
            detail=f"Plano invalido ou price nao configurado: {body.plan}",
        )

    if chave.tier in ("pro", "enterprise"):
        raise HTTPException(
            status_code=400,
            detail=f"Voce ja possui o plano {chave.tier}. Use o portal para gerenciar.",
        )

    try:
        customer_id = _obter_ou_criar_customer(chave)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{config.DASHBOARD_URL}/dashboard/settings?checkout=success",
            cancel_url=f"{config.DASHBOARD_URL}/dashboard/settings?checkout=cancel",
            metadata={
                "specter_key_id": str(chave.id),
                "plan": body.plan,
            },
            subscription_data={
                "metadata": {
                    "specter_key_id": str(chave.id),
                },
            },
        )

        log.info(
            "checkout_criado",
            email=chave.email,
            plan=body.plan,
            session_id=session.id,
        )

        return ResponseCheckout(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.StripeError as e:
        log.error("stripe_checkout_erro", erro=str(e))
        raise HTTPException(status_code=502, detail=f"Erro Stripe: {e.user_message}")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Recebe webhooks do Stripe.
    Eventos tratados:
      - checkout.session.completed → ativa Pro
      - customer.subscription.updated → sincroniza tier
      - customer.subscription.deleted → downgrade para free
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret nao configurado")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError:
        log.warning("webhook_assinatura_invalida")
        raise HTTPException(status_code=400, detail="Assinatura invalida")
    except ValueError:
        log.warning("webhook_payload_invalido")
        raise HTTPException(status_code=400, detail="Payload invalido")

    tipo = event["type"]
    dados = event["data"]["object"]

    log.info("webhook_recebido", tipo=tipo, event_id=event["id"])

    if tipo == "checkout.session.completed":
        _processar_checkout_completo(dados)

    elif tipo == "customer.subscription.updated":
        _processar_subscription_atualizada(dados)

    elif tipo == "customer.subscription.deleted":
        _processar_subscription_cancelada(dados)

    elif tipo == "invoice.payment_failed":
        _processar_pagamento_falhou(dados)

    return JSONResponse(content={"status": "ok"})


@router.get("/portal")
async def portal_stripe(chave: ChaveAPI = Depends(dependencia_api_key)):
    """Redireciona para o Stripe Customer Portal (gerenciar assinatura)."""
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe nao configurado")

    if not chave.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma assinatura encontrada. Faca upgrade primeiro.",
        )

    try:
        portal = stripe.billing_portal.Session.create(
            customer=chave.stripe_customer_id,
            return_url=f"{config.DASHBOARD_URL}/dashboard/settings",
        )
        return {"portal_url": portal.url}
    except stripe.StripeError as e:
        log.error("portal_erro", erro=str(e))
        raise HTTPException(status_code=502, detail=f"Erro Stripe: {e.user_message}")


def _processar_checkout_completo(session: dict) -> None:
    """Ativa tier Pro apos pagamento bem-sucedido."""
    key_id = session.get("metadata", {}).get("specter_key_id")
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")

    if not key_id:
        log.warning("checkout_sem_key_id", session_id=session.get("id"))
        return

    sessao_db = obter_sessao()
    try:
        registro = sessao_db.get(ChaveAPI, int(key_id))
        if not registro:
            log.warning("checkout_key_nao_encontrada", key_id=key_id)
            return

        registro.tier = "pro"
        registro.stripe_customer_id = customer_id
        registro.stripe_subscription_id = subscription_id
        sessao_db.commit()

        log.info(
            "tier_ativado_via_stripe",
            email=registro.email,
            tier="pro",
            subscription_id=subscription_id,
        )
    except Exception as e:
        sessao_db.rollback()
        log.error("checkout_completo_erro", erro=str(e))
    finally:
        sessao_db.close()


def _processar_subscription_atualizada(sub: dict) -> None:
    """Sincroniza tier quando assinatura muda (upgrade/downgrade)."""
    customer_id = sub.get("customer")
    status = sub.get("status")
    price_id = None

    items = sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")

    sessao_db = obter_sessao()
    try:
        registro = sessao_db.execute(
            select(ChaveAPI).where(ChaveAPI.stripe_customer_id == customer_id)
        ).scalar_one_or_none()

        if not registro:
            log.warning("sub_atualizada_customer_nao_encontrado", customer_id=customer_id)
            return

        if status == "active" and price_id:
            novo_tier = _TIER_POR_PRICE.get(price_id, "pro")
            registro.tier = novo_tier
            registro.stripe_subscription_id = sub.get("id")
            log.info("tier_sincronizado", email=registro.email, tier=novo_tier)
        elif status in ("past_due", "unpaid"):
            log.warning("pagamento_pendente", email=registro.email, status=status)
        elif status == "canceled":
            registro.tier = "free"
            registro.stripe_subscription_id = None
            log.info("tier_downgrade_cancelamento", email=registro.email)

        sessao_db.commit()
    except Exception as e:
        sessao_db.rollback()
        log.error("sub_atualizada_erro", erro=str(e))
    finally:
        sessao_db.close()


def _processar_subscription_cancelada(sub: dict) -> None:
    """Downgrade para free quando assinatura eh cancelada."""
    customer_id = sub.get("customer")

    sessao_db = obter_sessao()
    try:
        registro = sessao_db.execute(
            select(ChaveAPI).where(ChaveAPI.stripe_customer_id == customer_id)
        ).scalar_one_or_none()

        if not registro:
            return

        registro.tier = "free"
        registro.stripe_subscription_id = None
        sessao_db.commit()

        log.info("tier_downgrade_cancelado", email=registro.email)
    except Exception as e:
        sessao_db.rollback()
        log.error("sub_cancelada_erro", erro=str(e))
    finally:
        sessao_db.close()


def _processar_pagamento_falhou(invoice: dict) -> None:
    """Log quando pagamento falha (nao faz downgrade imediato)."""
    customer_id = invoice.get("customer")
    log.warning(
        "pagamento_falhou",
        customer_id=customer_id,
        amount=invoice.get("amount_due"),
        attempt=invoice.get("attempt_count"),
    )
