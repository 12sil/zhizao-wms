"""板块一：双向关联查询。仅展示，不保存、不修改任何业务数据。"""
import streamlit as st
import pandas as pd
from decimal import Decimal
from core.query import customer_trace, product_trace, order_history
from views.common import header, order_table, history_table, product_details


def render(store):
    header("01 / TRACEABILITY", "双向数据查询", "仓库/部门 → 物料 → 出入库流水；物料 → 仓库/部门 → 历史记录。此页面为纯查询。")
    data = store.read()
    keyword = st.text_input("快速检索", placeholder="输入仓库/部门名称、物料名称或物料编码")
    tab_c, tab_p = st.tabs(["👥 从仓库/部门追溯", "📚 从物料反查"])
    with tab_c:
        customers = [c for c in data["customers"] if not keyword or keyword.casefold() in c["name"].casefold()]
        if not customers:
            st.info("没有匹配仓库/部门，请调整检索内容或先建立仓库/部门档案。")
        else:
            selected = st.selectbox("选择仓库/部门", customers, format_func=lambda c: c["name"], key="trace_customer")
            st.write(f"负责人：{selected['contact'] or '未填写'}  |  电话：{selected['phone'] or '未填写'}")
            st.caption(f"上课 / 活动地点：{selected['address'] or '未填写'}")
            orders = customer_trace(data, selected["id"])
            a, b, c = st.columns(3)
            a.metric("历史出入库流水", len(orders))
            b.metric("分配物料种类", len({o["product_id"] for o in orders}))
            c.metric("涉及出入库流水月份", len({o["order_month"] for o in orders}))
            st.subheader("所有历史出入库流水")
            order_table(orders)
            st.markdown("#### 📊 仓库/部门各物料分配数量")
            st.caption("汇总该仓库/部门历史出入库流水数量，排除已取消出入库流水；不同单位分开展示。")
            # 使用物料 ID 与单位分组，避免同名物料或不同计量单位混加。
            totals = {}
            for order in orders:
                if order["status"] == "已取消":
                    continue
                key = (order["product_id"], order["unit"])
                if key not in totals:
                    totals[key] = {"物料": f"{order['current_product']} · {order['product_code']}",
                                   "单位": order["unit"], "分配数量": Decimal(0)}
                totals[key]["分配数量"] += Decimal(order["quantity"])
            if totals:
                frame = pd.DataFrame([{**row, "分配数量": float(row["分配数量"])} for row in totals.values()])
                for unit, group in frame.groupby("单位", sort=False):
                    st.caption(f"计量单位：{unit}")
                    st.bar_chart(group.set_index("物料")[["分配数量"]], color="#3158dd", height=280)
            else:
                st.info("该仓库/部门暂无可统计的分配数量。")
            # 物料展开详情与物料反查共用同一份资料，避免数据割裂。
            with st.expander("查看该仓库/部门涉及的物料资料"):
                ids = {o["product_id"] for o in orders}
                for product in data["products"]:
                    if product["id"] in ids:
                        product_details(product, store)
                        st.divider()
            with st.expander("执行与状态追溯记录"):
                history_table(order_history(data, {o["id"] for o in orders}))
    with tab_p:
        products = [p for p in data["products"] if not keyword or keyword.casefold() in (p["name"] + p["code"]).casefold()]
        if not products:
            st.info("没有匹配物料，请调整检索内容或先建立物料资料。")
        else:
            selected = st.selectbox("选择物料", products, format_func=lambda p: f"{p['code']} · {p['name']}", key="trace_product")
            orders = product_trace(data, selected["id"])
            st.markdown("#### 哪些仓库/部门关联过？")
            ids = {o["customer_id"] for o in orders}
            customers = [c for c in data["customers"] if c["id"] in ids]
            if customers:
                st.dataframe([{"仓库/部门": c["name"], "负责人": c["contact"], "电话": c["phone"],
                               "历史出入库流水数": sum(o["customer_id"] == c["id"] for o in orders)} for c in customers],
                              hide_index=True, use_container_width=True)
            else:
                st.info("该物料暂无分配记录。")
            st.subheader("该物料的所有历史出入库流水")
            order_table(orders)
            with st.expander("执行与状态追溯记录", expanded=False):
                history_table(order_history(data, {o["id"] for o in orders}))
            with st.expander("查看物料全套资料"):
                product_details(selected, store)


