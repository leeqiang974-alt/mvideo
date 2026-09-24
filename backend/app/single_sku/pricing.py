"""M.Video single-SKU pricing engine.

The pricing formula mirrors the approved MGlobal model, but uses Decimal for
exact money arithmetic. Source Ozon RUB prices are intentionally not accepted
here: only a human-confirmed CNY purchase cost may create a product cost.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Mapping

NO_BRAND = "Нет бренда"
TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")
ONE = Decimal("1")

DEFAULT_FX_USD_RUB = Decimal("95")
DEFAULT_FX_CNY_RUB = Decimal("13.2")
DEFAULT_ACQUIRING_RATE = Decimal("0.015")
DEFAULT_CROSS_BORDER_RATE = Decimal("0.01")
DEFAULT_HANDLING_USD = Decimal("0.5")
DEFAULT_TARGET_MARGIN = Decimal("0.25")

COMMISSION_RATES: dict[str, Decimal] = {
    "phones": Decimal("0.06"),
    "electronics": Decimal("0.10"),
    "fashion": Decimal("0.15"),
    "cosmetics": Decimal("0.13"),
    "perfume": Decimal("0.13"),
    "toys": Decimal("0.15"),
    "home": Decimal("0.15"),
    "other": Decimal("0.15"),
}
COMMISSION_ALIASES: dict[str, str] = {
    "phone": "phones",
    "mobile": "phones",
    "smartphone": "phones",
    "smartphones": "phones",
    "phones": "phones",
    "electronics": "electronics",
    "electronic": "electronics",
    "fashion": "fashion",
    "clothes": "fashion",
    "apparel": "fashion",
    "cosmetics": "cosmetics",
    "beauty": "cosmetics",
    "perfume": "perfume",
    "fragrance": "perfume",
    "toys": "toys",
    "toy": "toys",
    "home": "home",
    "household": "home",
    "homegoods": "home",
    "other": "other",
}

DEFAULT_CHANNEL_RATES: dict[str, dict[str, Decimal]] = {
    "economy": {"per_kg": Decimal("4.2"), "per_100g": Decimal("0.42")},
    "express": {"per_kg": Decimal("7.5"), "per_100g": Decimal("0.75")},
}

MAX_WEIGHT_KG = Decimal("30")
MAX_DIMENSION_SUM_CM = Decimal("200")
MAX_SIDE_CM = Decimal("110")


class PricingError(ValueError):
    """Raised when required pricing inputs are invalid or uneconomic."""


def to_decimal(value: Any, field: str, *, allow_none: bool = False) -> Decimal | None:
    """Convert finite numeric input to Decimal without float drift."""
    if value is None or value == "":
        if allow_none:
            return None
        raise PricingError(f"{field} is required")
    if isinstance(value, bool):
        raise PricingError(f"{field} must be numeric")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        result = Decimal(str(value))
    else:
        text = str(value).strip().replace(",", ".")
        try:
            result = Decimal(text)
        except Exception as exc:  # InvalidOperation and friends
            raise PricingError(f"{field} must be numeric") from exc
    if not result.is_finite():
        raise PricingError(f"{field} must be finite")
    return result


def require_rate(value: Any, field: str) -> Decimal:
    rate = to_decimal(value, field)
    if rate < ZERO or rate >= ONE:
        raise PricingError(f"{field} must be between 0 and 1")
    return rate


def normalize_commission_category(category: Any) -> str:
    key = str(category or "other").strip().lower()
    return COMMISSION_ALIASES.get(key, "other")


def normalize_shipping_channel(channel: Any) -> str:
    key = str(channel or "economy").strip().lower()
    if key not in DEFAULT_CHANNEL_RATES:
        raise PricingError("shipping_channel must be economy or express")
    return key


def physical_volume_l(
    length_cm: Decimal,
    width_cm: Decimal,
    height_cm: Decimal,
) -> Decimal:
    return length_cm * width_cm * height_cm / Decimal("1000")


def billable_volume_l(
    length_cm: Decimal,
    width_cm: Decimal,
    height_cm: Decimal,
) -> Decimal:
    raw = physical_volume_l(length_cm, width_cm, height_cm)
    if raw <= ZERO:
        return ZERO
    return max(ONE, raw.to_integral_value(rounding=ROUND_CEILING))


def validate_physical_limits(
    length_cm: Decimal,
    width_cm: Decimal,
    height_cm: Decimal,
    weight_kg: Decimal,
) -> list[str]:
    blockers: list[str] = []
    if weight_kg > MAX_WEIGHT_KG:
        blockers.append("包裹重量超过 30kg 限制")
    side_sum = length_cm + width_cm + height_cm
    if side_sum > MAX_DIMENSION_SUM_CM:
        blockers.append("三边之和超过 200cm 限制")
    if max(length_cm, width_cm, height_cm) > MAX_SIDE_CM:
        blockers.append("单边长度超过 110cm 限制")
    return blockers


def international_freight_usd(
    weight_g: Decimal,
    channel: str,
    channel_rates: Mapping[str, Mapping[str, Decimal]] | None = None,
) -> Decimal:
    """Calculate line-haul cost in USD. Under 1kg is rounded up per 100g."""
    if weight_g <= ZERO:
        raise PricingError("weight_g must be greater than zero")
    normalized_channel = normalize_shipping_channel(channel)
    rates = channel_rates or DEFAULT_CHANNEL_RATES
    selected = rates[normalized_channel]
    weight_kg = weight_g / Decimal("1000")
    if weight_kg < ONE:
        units = (weight_g / Decimal("100")).to_integral_value(rounding=ROUND_CEILING)
        return units * selected["per_100g"]
    return weight_kg * selected["per_kg"]


def local_delivery_rub(billable_volume: Decimal) -> Decimal:
    if billable_volume <= ZERO:
        return ZERO
    if billable_volume <= ONE:
        return Decimal("50")
    if billable_volume <= Decimal("2"):
        return Decimal("100")
    extra = billable_volume - Decimal("2")
    return min(Decimal("100") + extra * Decimal("4"), Decimal("1490"))


def calculate_price(
    *,
    purchase_cost_cny: Any,
    weight_g: Any,
    length_cm: Any,
    width_cm: Any,
    height_cm: Any,
    domestic_cost_cny: Any = ZERO,
    commission_category: Any = "other",
    target_net_margin: Any = DEFAULT_TARGET_MARGIN,
    shipping_channel: Any = "economy",
    acquiring_rate: Any = DEFAULT_ACQUIRING_RATE,
    cross_border_rate: Any = DEFAULT_CROSS_BORDER_RATE,
    ads_rate: Any = ZERO,
    return_loss_rate: Any = ZERO,
    label_fee_rub: Any = ZERO,
    fx_usd_rub: Any = DEFAULT_FX_USD_RUB,
    fx_cny_rub: Any = DEFAULT_FX_CNY_RUB,
    handling_usd: Any = DEFAULT_HANDLING_USD,
    channel_rates: Mapping[str, Mapping[str, Decimal]] | None = None,
) -> dict[str, Decimal]:
    """Return target RUB price and complete cost decomposition."""
    purchase = to_decimal(purchase_cost_cny, "purchase_cost_cny")
    domestic = to_decimal(domestic_cost_cny, "domestic_cost_cny")
    if purchase <= ZERO:
        raise PricingError("purchase_cost_cny must be greater than zero")
    if domestic < ZERO:
        raise PricingError("domestic_cost_cny cannot be negative")

    weight = to_decimal(weight_g, "weight_g")
    length = to_decimal(length_cm, "length_cm")
    width = to_decimal(width_cm, "width_cm")
    height = to_decimal(height_cm, "height_cm")
    if any(value <= ZERO for value in (weight, length, width, height)):
        raise PricingError("weight and dimensions must be greater than zero")

    weight_kg = weight / Decimal("1000")
    physical_errors = validate_physical_limits(length, width, height, weight_kg)
    if physical_errors:
        raise PricingError("; ".join(physical_errors))

    margin = require_rate(target_net_margin, "target_net_margin")
    commission_key = normalize_commission_category(commission_category)
    commission_rate = COMMISSION_RATES[commission_key]
    acquiring = require_rate(acquiring_rate, "acquiring_rate")
    cross_border = require_rate(cross_border_rate, "cross_border_rate")
    ads = require_rate(ads_rate, "ads_rate")
    returns = require_rate(return_loss_rate, "return_loss_rate")
    label_fee = to_decimal(label_fee_rub, "label_fee_rub")
    if label_fee < ZERO:
        raise PricingError("label_fee_rub cannot be negative")

    fx_usd = to_decimal(fx_usd_rub, "fx_usd_rub")
    fx_cny = to_decimal(fx_cny_rub, "fx_cny_rub")
    handling = to_decimal(handling_usd, "handling_usd")
    if fx_usd <= ZERO or fx_cny <= ZERO or handling < ZERO:
        raise PricingError("currency and handling parameters must be valid")

    volume = billable_volume_l(length, width, height)
    goods_cost_rub = (purchase + domestic) * fx_cny
    freight_usd = international_freight_usd(weight, shipping_channel, channel_rates)
    freight_rub = freight_usd * fx_usd
    handling_rub = handling * fx_usd
    local_rub = local_delivery_rub(volume)

    variable_rate = commission_rate + acquiring + cross_border + ads + returns
    fixed_cost_rub = freight_rub + handling_rub + local_rub + label_fee + goods_cost_rub
    break_even_denominator = ONE - variable_rate
    target_denominator = break_even_denominator - margin
    if break_even_denominator <= ZERO:
        raise PricingError("变动成本率过高，无法计算保本售价")
    if target_denominator <= ZERO:
        raise PricingError("目标净利率净利率过高，无法计算目标售价")

    break_even_price = fixed_cost_rub / break_even_denominator
    target_price = fixed_cost_rub / target_denominator

    return {
        "commission_category": commission_key,
        "shipping_channel": normalize_shipping_channel(shipping_channel),
        "price_rub": target_price.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "break_even_price_rub": break_even_price.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "weight_g": weight,
        "weight_kg": weight_kg,
        "length_cm": length,
        "width_cm": width,
        "height_cm": height,
        "physical_volume_l": physical_volume_l(length, width, height),
        "billable_volume_l": volume,
        "goods_cost_rub": goods_cost_rub,
        "international_freight_usd": freight_usd,
        "international_freight_rub": freight_rub,
        "handling_usd": handling,
        "handling_rub": handling_rub,
        "local_delivery_rub": local_rub,
        "label_fee_rub": label_fee,
        "fixed_cost_rub": fixed_cost_rub,
        "commission_rate": commission_rate,
        "acquiring_rate": acquiring,
        "cross_border_rate": cross_border,
        "ads_rate": ads,
        "return_loss_rate": returns,
        "variable_cost_rate": variable_rate,
        "target_net_margin": margin,
        "fx_usd_rub": fx_usd,
        "fx_cny_rub": fx_cny,
    }


def pricing_json_safe(value: Any) -> Any:
    """Convert Decimal values in a pricing result to JSON-safe strings."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): pricing_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [pricing_json_safe(item) for item in value]
    return value
