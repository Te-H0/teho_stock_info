"""signals.yaml 기준 시그널 평가. 결과는 ID 리스트 + 점수 합."""

import operator

_OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq}


def _match(cond: dict, metrics: dict) -> bool:
    # 1) expression 방식
    if "expression" in cond:
        try:
            return bool(eval(cond["expression"], {"__builtins__": {}}, metrics))  # noqa: S307 (config 신뢰)
        except TypeError:
            return False  # metric이 None(기간부족 등) → 평가 불가, 정상
        except NameError as e:
            # signals.yaml expression에 오타로 없는 metric명 → 조용히 묻히면 안 됨
            print(f"[signals.yaml expression 오류] '{cond['expression']}': {e}")
            return False
    # 2) metric op value / compareTo 방식
    metric = metrics.get(cond["metric"])
    if metric is None:
        return False
    op = _OPS[cond["op"]]
    if "compareTo" in cond:
        other = metrics.get(cond["compareTo"])
        if other is None:
            return False
        return op(metric, other)
    return op(metric, cond["value"])


def _evaluate(defs: list[dict], metrics: dict, country: str | None = None) -> tuple[list[str], int]:
    ids, score = [], 0
    for sig in defs:
        markets = sig.get("markets")          # 특정 시장 전용 시그널 (예: KR만)
        if markets and country and country not in markets:
            continue
        if _match(sig["condition"], metrics):
            ids.append(sig["id"])
            score += sig["score"]
    return ids, score


def evaluate_stock(metrics: dict, signals_cfg: dict, country: str | None = None) -> tuple[list[str], int]:
    return _evaluate(signals_cfg["stockSignals"], metrics, country)


def evaluate_sector(metrics: dict, signals_cfg: dict, country: str | None = None) -> tuple[list[str], int]:
    return _evaluate(signals_cfg["sectorSignals"], metrics, country)
