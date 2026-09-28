"""库存阈值预警规则。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from config import STATUSES, SAFETY_STOCK, LOW_STOCK

URGENT = "🔴 紧急备货（高风险）"
LOW = "🟡 库存偏低（临期）"
SAFE = "🟢 库存安全"

def today_china():
    return datetime.now(timezone(timedelta(hours=8))).date()

def timestamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")

def parse_date(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    try: return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError): raise ValueError("日期必须是完整有效日期，例如 2026-09-20。") from None

def quantity_text(value):
    try: number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError): raise ValueError("数量必须是大于 0 的数字。") from None
    if not number.is_finite() or number <= 0 or number > 100000000: raise ValueError("数量必须大于 0，且不超过一亿。")
    if number.as_tuple().exponent < -3: raise ValueError("数量最多保留三位小数。")
    return format(number.normalize(), "f")

def warning(stock, status="入库", today=None):
    try: value = Decimal(str(stock or 0))
    except InvalidOperation: value = Decimal(0)
    if status == "已取消":
        return {"label": "—已取消", "level": "closed", "stock": float(value), "rank": 4}
    if value < SAFETY_STOCK: label, level, rank = URGENT, "urgent", 0
    elif value <= LOW_STOCK: label, level, rank = LOW, "low", 1
    else: label, level, rank = SAFE, "safe", 2
    return {"label": label, "level": level, "stock": float(value), "rank": rank}

