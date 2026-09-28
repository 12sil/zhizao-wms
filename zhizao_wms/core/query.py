"""库存查询层。"""
from decimal import Decimal
from core.rules import warning

def enriched_orders(data, today=None):
    customers = {c["id"]: c for c in data["customers"]}; products = {p["id"]: p for p in data["products"]}; result=[]
    for row in data["orders"]:
        x=dict(row); p=products.get(x["product_id"], {})
        x["current_customer"] = customers.get(x["customer_id"], {}).get("name", x["customer_name"])
        x["current_product"] = p.get("name", x["product_name"]); x["current_stock"] = p.get("current_stock", "0")
        x.update(warning(x["current_stock"], x["status"], today)); result.append(x)
    return sorted(result, key=lambda r:(r["rank"], r["current_stock"], r["id"]))

def customer_trace(data, customer_id, today=None): return [o for o in enriched_orders(data,today) if o["customer_id"]==customer_id]
def product_trace(data, product_id, today=None): return [o for o in enriched_orders(data,today) if o["product_id"]==product_id]
def order_history(data, ids): return sorted([dict(h) for h in data["history"] if h["order_id"] in ids], key=lambda h:h["created_at"], reverse=True)
def shipped_summary(data, month):
    summary={}
    for o in enriched_orders(data):
        if o["status"] not in ("入库","出库") or not o["created_at"].startswith(month): continue
        key=(o["customer_id"],o["unit"]); summary.setdefault(key,{"仓库/部门":o["current_customer"],"单位":o["unit"],"流水笔数":0,"数量":Decimal(0)})
        summary[key]["流水笔数"]+=1; summary[key]["数量"]+=Decimal(o["quantity"])
    return [{**row,"数量":format(row["数量"],"f")} for row in summary.values()]

