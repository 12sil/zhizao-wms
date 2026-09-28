"""智造WMS库存阈值预警看板。"""
import streamlit as st
import pandas as pd
import plotly.express as px
from core.query import enriched_orders
from core.rules import SAFETY_STOCK, LOW_STOCK
from views.common import header, order_table, notify

def render(store):
    header("02 / INVENTORY CONTROL", "库存驾驶舱 · 补货预警中心", f"安全库存 {SAFETY_STOCK:,} · 库存偏低区间 {SAFETY_STOCK:,}–{LOW_STOCK:,} · 超过 {LOW_STOCK:,} 为安全")
    notify(); data=store.read(); orders=enriched_orders(data)
    products=data["products"]
    levels={"urgent":sum(float(p.get("current_stock") or 0)<SAFETY_STOCK for p in products), "low":sum(SAFETY_STOCK<=float(p.get("current_stock") or 0)<=LOW_STOCK for p in products), "safe":sum(float(p.get("current_stock") or 0)>LOW_STOCK for p in products)}
    a,b,c=st.columns(3); a.metric("🔴 紧急备货（高风险）",levels["urgent"]); b.metric("🟡 库存偏低（临期）",levels["low"]); c.metric("🟢 库存安全",levels["safe"])
    st.caption("判断口径固定为物料当前库存：低于 10,000 为高风险，10,000–15,000 为临期，超过 15,000 为安全。")
    total_stock=sum(float(p.get("current_stock") or 0) for p in products)
    m1,m2,m3=st.columns(3)
    m1.metric("物料品种",len(products)); m2.metric("库存总量",f"{total_stock:,.0f}"); m3.metric("待补货品种",levels["urgent"]+levels["low"])
    chart=pd.DataFrame({"物料数量":[levels["urgent"],levels["low"],levels["safe"]]},index=["紧急备货","库存偏低","库存安全"])
    st.bar_chart(chart,y="物料数量",color="#78b9d4",height=250)
    left,right=st.columns(2)
    with left:
        fig=px.pie(chart.reset_index(names="状态"),names="状态",values="物料数量",hole=.62,color="状态",color_discrete_map={"紧急备货":"#d98f87","库存偏低":"#d8b36b","库存安全":"#78b895"})
        fig.update_layout(height=300,margin=dict(l=10,r=10,t=20,b=20),paper_bgcolor="rgba(0,0,0,0)",showlegend=True)
        st.plotly_chart(fig,use_container_width=True,key="stock_ring")
    with right:
        st.markdown("#### 物料库存分布")
        rows=[{"物料编码":p["code"],"物料":p["name"],"当前库存":p.get("current_stock","0"),"单位":p["unit"],"状态":next((o["label"] for o in orders if o["product_id"]==p["id"]),"—")} for p in products]
        st.dataframe(rows,hide_index=True,use_container_width=True)
    st.divider(); st.subheader("出入库流水")
    q=st.text_input("筛选流水",placeholder="仓库/部门、物料、编码或流水编号")
    filtered=[o for o in orders if q.casefold() in " ".join((o["current_customer"],o["current_product"],o["product_code"],o["id"])).casefold()]
    order_table(filtered,"暂无匹配出入库流水。")
    with st.expander("补货优先清单",expanded=bool(levels["urgent"])):
        low=[o for o in orders if o["level"] in ("urgent","low")]
        order_table(low,"当前没有低库存物料。")


