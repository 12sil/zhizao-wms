import streamlit as st
from core.rules import today_china
from core.query import enriched_orders
from core.service import create_order
from views.common import header, order_table, notify, saved

def render(store):
    header("STOCK MOVEMENT","出入库流水管理","登记入库或出库数量，系统自动同步物料当前库存。"); notify(); data=store.read()
    if not data["customers"] or not data["products"]: st.info("请先建立仓库/部门和物料档案。"); return
    with st.form("movement_form"):
        warehouse=st.selectbox("仓库 / 部门",data["customers"],format_func=lambda c:c["name"]); material=st.selectbox("物料",data["products"],format_func=lambda p:f"{p['code']} · {p['name']}（当前 {p.get('current_stock','0')} {p['unit']}）"); kind=st.radio("流水类型",["入库","出库"],horizontal=True); qty=st.number_input("数量",min_value=0.001,value=1.0,step=1.0); notes=st.text_area("备注"); submit=st.form_submit_button("保存出入库流水",type="primary")
    if submit:
        try: create_order(store,{"customer_id":warehouse["id"],"product_id":material["id"],"quantity":qty,"status":kind,"delivery_deadline":today_china(),"notes":notes}); saved("出入库流水已保存，物料库存已同步更新。")
        except ValueError as exc: st.error(str(exc))
    st.divider(); st.subheader("最近流水"); order_table(enriched_orders(data)[:30],"暂无出入库流水。")

