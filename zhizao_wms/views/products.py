import streamlit as st
from core.service import save_product, save_image
from views.common import header, product_details, notify, saved

def render(store):
    header("MATERIAL MASTER DATA","物料资料库","维护物料编码、规格、当前库存和补货阈值状态。"); notify(); products=store.read()["products"]
    query=st.text_input("搜索物料",placeholder="物料名称 / 物料编码"); filtered=[p for p in products if query.casefold() in (p["name"]+p["code"]).casefold()]
    if not filtered: st.info("暂无匹配物料，可在下方新增资料。")
    for product in filtered:
        with st.expander(f"📦 {product['name']} | {product['code']} | 当前库存 {product.get('current_stock','0')} {product['unit']}"): product_details(product,store)
    st.divider(); mode=st.radio("资料操作",["新增物料","修改物料资料"],horizontal=True); row={}
    if mode=="修改物料资料":
        if not products: st.info("暂无可修改物料。"); return
        row=st.selectbox("选择物料资料",products,format_func=lambda p:f"{p['code']} · {p['name']}")
    with st.form("product_form"):
        a,b,c=st.columns([2,2,1]); values={}; values["name"]=a.text_input("物料名称 *",row.get("name",""),max_chars=100); values["code"]=b.text_input("物料编码 *",row.get("code",""),max_chars=100); values["unit"]=c.text_input("计量单位 *",row.get("unit","pcs"),max_chars=15)
        values["current_stock"]=st.number_input("当前库存",min_value=0.0,value=float(row.get("current_stock",0) or 0),step=100.0)
        image=st.file_uploader("上传物料图片（可选）",type=["png","jpg","jpeg","webp"]); values["description"]=st.text_area("物料介绍",row.get("description",""),max_chars=6000)
        a,b=st.columns(2); values["specs"]=a.text_area("规格参数",row.get("specs",""),height=110,max_chars=6000); values["checklist"]=b.text_area("质检要求（每行一项）",row.get("checklist",""),height=110,max_chars=6000); values["bom"]=st.text_area("供应与使用说明",row.get("bom",""),max_chars=12000)
        submit=st.form_submit_button("保存物料资料",type="primary")
    if submit:
        try:
            values["image_path"]=save_image(store,image.getvalue()) if image else row.get("image_path",""); save_product(store,values,row.get("id")); saved("物料资料已保存。")
        except ValueError as exc: st.error(str(exc))

