"""基础仓库/部门档案维护，独立于只读追溯页面。"""
import streamlit as st
from core.service import save_customer
from views.common import header, notify, saved


def render(store):
    header("COURSES / PROJECTS", "仓库/部门档案管理", "统一仓库/部门档案，以稳定编号关联所有物料与出入库流水。")
    notify()
    data = store.read()
    query = st.text_input("搜索仓库/部门档案", placeholder="仓库/部门名称 / 负责人 / 电话")
    rows = [c for c in data["customers"] if query.casefold() in " ".join((c["name"], c["contact"], c["phone"])).casefold()]
    st.metric("仓库/部门档案总数", len(data["customers"]))
    if rows:
        st.dataframe([{"仓库/部门编号": c["id"], "仓库/部门名称": c["name"], "负责人": c["contact"], "电话": c["phone"], "上课 / 活动地点": c["address"]} for c in rows], hide_index=True, use_container_width=True)
    mode = st.radio("档案操作", ["新增仓库/部门", "修改仓库/部门"], horizontal=True)
    row = {}
    if mode == "修改仓库/部门":
        if not data["customers"]:
            st.info("暂无可修改仓库/部门。")
            return
        row = st.selectbox("选择仓库/部门档案", data["customers"], format_func=lambda c: c["name"])
    with st.form("customer_form"):
        a, b = st.columns(2)
        values = {}
        values["name"] = a.text_input("仓库/部门名称 *", row.get("name", ""), max_chars=100)
        values["contact"] = b.text_input("负责人", row.get("contact", ""), max_chars=100)
        values["phone"] = a.text_input("联系电话", row.get("phone", ""), max_chars=50)
        values["address"] = b.text_input("上课 / 活动地点", row.get("address", ""), max_chars=500)
        values["notes"] = st.text_area("档案备注", row.get("notes", ""), max_chars=2000)
        submit = st.form_submit_button("保存仓库/部门档案", type="primary")
    if submit:
        try:
            save_customer(store, values, row.get("id"))
            saved("仓库/部门档案已保存，历史关联保持不变。")
        except ValueError as exc:
            st.error(str(exc))




