from __future__ import annotations


class UniverseSelectorError(ValueError):
    pass


def asset_matches_selector(asset: dict, selector: dict) -> bool:
    include = selector.get("include", {})
    exclude = selector.get("exclude", {})
    if not isinstance(include, dict) or not isinstance(exclude, dict):
        raise UniverseSelectorError("include/exclude must be objects")
    return _matches_group(asset, include, include_mode=True) and not _matches_group(asset, exclude, include_mode=False)


def resolve_selector(assets: list[dict], selector: dict) -> list[dict]:
    seen = set()
    result = []
    for asset in assets:
        if asset_matches_selector(asset, selector):
            asset_id = asset.get("asset_id")
            if asset_id not in seen:
                seen.add(asset_id)
                result.append(asset)
    return result


def resolve_all_selectors(assets: list[dict], selectors: dict) -> dict[str, list[dict]]:
    return {
        name: resolve_selector(assets, selector)
        for name, selector in selectors.items()
    }


def _matches_group(asset: dict, group: dict, *, include_mode: bool) -> bool:
    if not group:
        return False if not include_mode else True
    results = []
    for field, condition in group.items():
        if field == "asset_ids":
            raise UniverseSelectorError("asset_ids buckets are not supported")
        if field == "tradability":
            results.append(_matches_nested_tradability(asset, condition))
        elif isinstance(condition, dict) and set(condition).issubset({"all", "any"}):
            results.append(_matches_list_condition(_asset_value(asset, field), condition))
        elif isinstance(condition, dict):
            raise UniverseSelectorError(f"unknown selector syntax for {field}")
        else:
            results.append(_asset_value(asset, field) == condition)
    return all(results) if include_mode else any(results)


def _matches_nested_tradability(asset: dict, condition: dict) -> bool:
    if not isinstance(condition, dict):
        raise UniverseSelectorError("tradability selector must be an object")
    tradability = asset.get("tradability") or {}
    results = []
    for field, expected in condition.items():
        value = tradability.get(field)
        if isinstance(expected, dict) and set(expected).issubset({"all", "any"}):
            results.append(_matches_list_condition(value, expected))
        elif isinstance(expected, dict):
            raise UniverseSelectorError(f"unknown tradability selector syntax for {field}")
        else:
            results.append(value == expected)
    return all(results)


def _matches_list_condition(value, condition: dict) -> bool:
    values = value if isinstance(value, list) else [value]
    values = set(values)
    if "all" in condition:
        expected = condition["all"]
        if not isinstance(expected, list):
            raise UniverseSelectorError("all condition must be a list")
        if not set(expected).issubset(values):
            return False
    if "any" in condition:
        expected = condition["any"]
        if not isinstance(expected, list):
            raise UniverseSelectorError("any condition must be a list")
        if not values.intersection(expected):
            return False
    return True


def _asset_value(asset: dict, field: str):
    if field in asset:
        return asset[field]
    exposures = asset.get("exposures")
    if isinstance(exposures, dict) and field in exposures:
        return exposures[field]
    return None
