from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


def _a_entero(valor):
    try:
        numero = Decimal(str(valor or 0))
    except (InvalidOperation, TypeError, ValueError):
        numero = Decimal("0")
    return int(numero.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@register.filter
def pesos(valor):
    return f"{_a_entero(valor):,}".replace(",", ".")


@register.filter
def entero(valor):
    if valor in (None, ""):
        return ""
    return str(_a_entero(valor))
