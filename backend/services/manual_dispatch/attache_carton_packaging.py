"""Conservative Attaché shipping-carton normalization using existing product fields."""
from decimal import Decimal, InvalidOperation
import re


INNER_BAGS_PER_CARTON = 14
_BAG_WEIGHT = re.compile(r"BAG\s*1\.50*", re.IGNORECASE)
_PRODUCT_WEIGHT = re.compile(r"(?<![0-9.])([0-9]+(?:\.[0-9]+)?)\s*KG\b", re.IGNORECASE)


def is_1_5kg_bag_package(unit):
    return bool(_BAG_WEIGHT.fullmatch(str(unit or "").strip()))


def _value(line, name):
    return line.get(name) if isinstance(line, dict) else getattr(line, name, None)


def _whole(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return int(number) if number.is_finite() and number > 0 and number == number.to_integral_value() else None


def _is_1_5kg_bag_product(line):
    identity = " ".join(str(_value(line, name) or "") for name in ("product_code", "product_name"))
    return (str(_value(line, "unit") or "").strip().upper() in {"BAG", "BAGS"}
            and {Decimal(match) for match in _PRODUCT_WEIGHT.findall(identity)} == {Decimal("1.5")})


def cartonized_inner_bag_quantity(line):
    """Recover original inner bags only for the reconciled shipping representation."""
    bags = _whole(_value(line, "quantity"))
    cartons = _whole(_value(line, "package_quantity"))
    if (_is_1_5kg_bag_product(line) and bags is not None and cartons is not None
            and str(_value(line, "package_unit") or "").strip().upper() == "CARTON"
            and bags == cartons * INNER_BAGS_PER_CARTON):
        return bags
    return None


def cartonized_product_weight_kg(line):
    # Stock weight follows original bags even if shipping Cartons are later edited.
    if (not _is_1_5kg_bag_product(line)
            or str(_value(line, "package_unit") or "").strip().upper() != "CARTON"):
        return None
    bags = _whole(_value(line, "quantity"))
    return bags * 1.5 if bags is not None else None


def normalize_attache_carton_packages(products, *, pallet_quantity, loose_bags_quantity,
                                     carton_quantity, companion_counts, carton_rows,
                                     source_requires_review=False):
    """Keep actual BAG counts; use the packaging pair for verified shipping Cartons.

    Conversion requires actual and companion bag counts to be identical, so the
    original inner-package count remains explicitly available in quantity/unit.
    Ambiguous inputs are returned without changing any product field.
    """
    # Existing pallet-only invoices make no carton claim and need no new warning.
    if not carton_quantity and pallet_quantity:
        return products, []
    candidates = [line for line in products if is_1_5kg_bag_package(line.get("package_unit"))
                  or _is_1_5kg_bag_product(line)]
    if not candidates and not (carton_quantity and not products):
        return products, []
    reason = None
    quantities = []
    if not products:
        reason = "no identifiable product accompanies the CTN total"
    elif pallet_quantity or loose_bags_quantity:
        reason = "mixed pallet or loose-bag loads do not establish carton allocation"
    elif _whole(carton_quantity) is None or carton_rows != 1:
        reason = "one compatible CTN total is required"
    elif source_requires_review or len(candidates) != len(products):
        reason = "mixed or unrecognized source rows make carton allocation ambiguous"
    else:
        for index, line in enumerate(products):
            bags = _whole(line.get("quantity"))
            packages = _whole(line.get("package_quantity"))
            if (not _is_1_5kg_bag_product(line)
                    or not is_1_5kg_bag_package(line.get("package_unit"))
                    or companion_counts.get(index) != 1):
                reason = "each 1.5kg bag product needs exactly one companion BAG1.5 row"
                break
            if bags is None or bags != packages or bags % INNER_BAGS_PER_CARTON:
                reason = "original bag and packaging counts must agree and be divisible by 14"
                break
            quantities.append(bags // INNER_BAGS_PER_CARTON)
        if reason is None and sum(quantities) != carton_quantity:
            reason = "derived product Cartons do not reconcile with the CTN total"
    if reason:
        return products, [f"Carton allocation requires review: {reason}; original product quantities retained."]
    return [dict(line, package_quantity=cartons, package_unit="CARTON")
            for line, cartons in zip(products, quantities)], []
