from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.auth import require_bearer
from app.credits import apify_is_enabled
from app.gtin import is_valid_gtin, normalize_gtin
from app.live_google import resolve_live
from app.models import (
    ConfirmRequest,
    ConfirmResponse,
    ErrorBody,
    InvalidateResponse,
    NameChoice,
    PriceChoice,
    ProductResponse,
    WeightChoice,
)
from app.resolve_samples import resolve_from_samples
from app import store

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="GTIN Product API", version="0.9.1")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def ui() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "apify_enabled": apify_is_enabled(),
        "mode": "cache-then-live",
        "live": "on cache miss only",
        "db": store.backend_name(),
    }


@app.get(
    "/v1/products/{gtin}",
    response_model=ProductResponse,
    responses={
        400: {"model": ErrorBody},
        401: {"model": ErrorBody},
        404: {"model": ErrorBody},
    },
)
def get_product(
    gtin: str,
    _token: str = Depends(require_bearer),
) -> ProductResponse | JSONResponse:
    digits = normalize_gtin(gtin)
    if not is_valid_gtin(digits):
        return JSONResponse(
            status_code=400,
            content=ErrorBody(error="invalid_gtin", gtin=gtin, detail="Failed format or checksum").model_dump(),
        )

    confirmed = store.get_product(digits)
    if confirmed is not None and _confirmed_complete(confirmed):
        return _as_response(store.product_as_lookup(confirmed), cache="hit")

    cached = store.get_lookup(digits)
    if cached is not None and _lookup_complete(cached["payload"]):
        return _as_response(cached["payload"], cache="hit", gtin=digits)

    resolved = _fetch(digits)
    if isinstance(resolved, JSONResponse):
        return resolved
    store.save_lookup(digits, resolved)
    return _as_response(resolved, cache=resolved.get("cache") or "sample")


@app.delete(
    "/v1/products/{gtin}/cache",
    response_model=InvalidateResponse,
    responses={
        400: {"model": ErrorBody},
        401: {"model": ErrorBody},
    },
)
def invalidate_cache(
    gtin: str,
    _token: str = Depends(require_bearer),
) -> InvalidateResponse | JSONResponse:
    digits = normalize_gtin(gtin)
    if not is_valid_gtin(digits):
        return JSONResponse(
            status_code=400,
            content=ErrorBody(error="invalid_gtin", gtin=gtin, detail="Failed format or checksum").model_dump(),
        )
    result = store.delete_cache(digits, master=True)
    return InvalidateResponse(
        gtin=digits,
        lookup=result["lookup"],
        master=result["master"],
    )


def _confirmed_complete(product: dict) -> bool:
    return bool(product.get("name")) and product.get("price") is not None and product.get("weight") is not None


def _lookup_complete(payload: dict) -> bool:
    return bool(payload.get("name")) and bool(payload.get("price")) and bool(payload.get("weight"))


def _as_response(payload: dict, cache: str, gtin: str | None = None) -> ProductResponse:
    return ProductResponse(
        gtin=payload.get("gtin") or gtin,
        name=payload.get("name") or [],
        name_source=payload.get("name_source") or [],
        price=payload.get("price") or [],
        price_source=payload.get("price_source") or [],
        weight=payload.get("weight") or [],
        weight_source=payload.get("weight_source") or [],
        cache=cache,
    )


def _fetch(digits: str) -> dict | JSONResponse:
    used_live = False
    if apify_is_enabled():
        used_live = True
        resolved = resolve_live(digits)
    else:
        resolved = resolve_from_samples(digits)
    return _error_or_resolved(resolved, digits, used_live)


def _error_or_resolved(
    resolved: dict,
    digits: str,
    used_live: bool,
) -> dict | JSONResponse:
    err = resolved.get("error")
    if err in {"apify_disabled", "missing_apify_token"}:
        return JSONResponse(
            status_code=503,
            content=ErrorBody(error=err, gtin=digits).model_dump(),
        )
    if err in {"no_local_sample", "not_found"}:
        detail = (
            "Live Google search found no product"
            if used_live
            else "No data found for this GTIN in local samples"
        )
        raise HTTPException(status_code=404, detail=detail)
    if err == "invalid_gtin":
        return JSONResponse(
            status_code=400,
            content=ErrorBody(error="invalid_gtin", gtin=digits).model_dump(),
        )
    return resolved


def _choice_source(choice, custom_label: str = "user") -> str | None:
    if not _choice_has_value(choice):
        return None
    if choice.custom or not choice.source:
        return custom_label
    return choice.source


def _choice_has_value(choice) -> bool:
    if isinstance(choice, PriceChoice):
        return choice.amount is not None
    if isinstance(choice, WeightChoice):
        return choice.value is not None
    if isinstance(choice, NameChoice):
        return bool((choice.value or "").strip())
    return False


@app.post(
    "/v1/products/{gtin}/confirm",
    response_model=ConfirmResponse,
    responses={
        400: {"model": ErrorBody},
        401: {"model": ErrorBody},
    },
)
def confirm_product(
    gtin: str,
    body: ConfirmRequest,
    _token: str = Depends(require_bearer),
) -> ConfirmResponse | JSONResponse:
    digits = normalize_gtin(gtin)
    if not is_valid_gtin(digits):
        return JSONResponse(
            status_code=400,
            content=ErrorBody(error="invalid_gtin", gtin=gtin, detail="Failed format or checksum").model_dump(),
        )

    name_source = _choice_source(body.name)
    price_source = _choice_source(body.price)
    weight_source = _choice_source(body.weight)

    product = store.save_product(
        digits,
        {
            "name": body.name.value,
            "price": {"amount": body.price.amount, "currency": body.price.currency}
            if body.price.amount is not None
            else None,
            "weight": {"value": body.weight.value, "unit": body.weight.unit or "g"}
            if body.weight.value is not None
            else None,
        },
        {"name": name_source, "price": price_source, "weight": weight_source},
    )
    return ConfirmResponse(gtin=digits, product=product, confidence=store.all_confidence())
