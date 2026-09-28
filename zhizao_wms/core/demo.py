"""仓储演示数据。"""
from datetime import timedelta
from core.rules import timestamp, today_china
from core.service import _add_order, uid

def reset_demo_orders(store):
    with store.transaction() as data:
        data["orders"] = []; data["history"] = []; data["imports"] = []
        for i, (product, qty, kind) in enumerate([(0, 1800, "出库"), (1, 3000, "出库"), (2, 1200, "入库"), (3, 500, "出库")]):
            _add_order(data, {"customer_id": data["customers"][i % len(data["customers"])]["id"], "product_id": data["products"][product]["id"], "quantity": qty, "status": kind, "delivery_deadline": today_china(), "notes": "一键加载的仓储演示流水"}, source="演示数据")

def seed_demo(store):
    with store.transaction() as data:
        if any(data.values()): return
        warehouses = [("华东一号仓", "张主管", "", "上海 · 浦东仓储中心"), ("生产一部", "李主管", "", "苏州 · 制造基地"), ("研发物料中心", "王工", "", "杭州 · 研发园区"), ("华南成品仓", "陈主管", "", "深圳 · 宝安仓储中心")]
        for name, contact, phone, address in warehouses:
            data["customers"].append({"id": uid("C"), "name": name, "contact": contact, "phone": phone, "address": address, "notes": "智造WMS演示仓库/部门", "created_at": timestamp()})
        materials = [("MAT-AL-001", "6061铝合金板材", "kg", "结构件加工常用铝板。", "厚度：3mm\n材质：6061-T6", "规格与批次核对\n来料检验合格" , 6800), ("MAT-IC-002", "工业控制芯片", "pcs", "自动化控制柜核心芯片。", "封装：LQFP\n等级：工业级", "型号核对\n防静电包装", 12600), ("MAT-BT-003", "锂电池保护板", "pcs", "储能设备配套保护板。", "电压：48V\n持续电流：30A", "电压测试\n外观检查", 18200), ("MAT-SC-004", "不锈钢紧固件", "box", "设备装配标准紧固件。", "规格：M6\n材质：304不锈钢", "数量清点\n防锈包装", 9200)]
        for code, name, unit, desc, specs, checklist, stock in materials:
            data["products"].append({"id": uid("P"), "code": code, "name": name, "unit": unit, "description": desc, "specs": specs, "bom": "", "checklist": checklist, "image_path": "", "current_stock": str(stock), "created_at": timestamp()})
        for i, (product, qty, kind) in enumerate([(0, 1800, "出库"), (1, 3000, "入库"), (2, 1200, "出库"), (3, 500, "出库"), (0, 600, "入库")]):
            _add_order(data, {"customer_id": data["customers"][i % 4]["id"], "product_id": data["products"][product]["id"], "quantity": qty, "status": kind, "delivery_deadline": today_china(), "notes": "智造WMS演示出入库流水"}, source="演示数据")

