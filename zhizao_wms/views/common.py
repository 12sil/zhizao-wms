"""共用页面元素。"""
import html
import pandas as pd
import streamlit as st
from core.rules import URGENT, LOW, SAFE

def header(kicker,title,subtitle):
    st.markdown(f'<div class="kicker">{html.escape(kicker)}</div>',unsafe_allow_html=True); st.title(title); st.caption(subtitle)
def order_frame(orders):
    return pd.DataFrame([{"流水编号":o["id"],"仓库/部门":o["current_customer"],"物料":o["current_product"],"物料编码":o["product_code"],"流水类型":o["status"],"数量":o["quantity"],"单位":o["unit"],"当前库存":o.get("current_stock","0"),"库存预警":o["label"],"记录时间":o["created_at"]} for o in orders])
def order_table(orders,empty="暂无出入库流水记录。"):
    if not orders: st.info(empty); return
    frame=order_frame(orders)
    def paint(row):
        color={URGENT:"#f7e1df",LOW:"#fbf0d7",SAFE:"#e2f1e7"}.get(row["库存预警"],"")
        return [f"background-color:{color}; color:#46515e" if color else "" for _ in row]
    st.dataframe(frame.style.apply(paint,axis=1),hide_index=True,use_container_width=True)
def history_table(history):
    if not history: st.info("暂无库存变更记录。"); return
    st.dataframe(pd.DataFrame(history).rename(columns={"order_id":"流水编号","from_status":"原状态","to_status":"新状态","note":"变更说明","created_at":"记录时间"}).drop(columns=["id","shipped_date","delivered_date"],errors="ignore"),hide_index=True,use_container_width=True)
def product_details(product,store):
    st.subheader(product["name"]); st.caption(f"物料编码：{product['code']} · 单位：{product['unit']} · 当前库存：{product.get('current_stock','0')}"); st.write(product.get("description") or "尚未填写物料介绍。"); st.markdown("**规格参数**"); st.text(product.get("specs") or "尚未填写规格参数。"); st.markdown("**质检要求**"); st.text(product.get("checklist") or "尚未填写质检要求。"); st.markdown("**当前库存**"); st.metric("库存数量",product.get("current_stock","0"))
def notify():
    if "flash" in st.session_state: st.success(st.session_state.pop("flash"))
def saved(message): st.session_state["flash"]=message; st.rerun()

