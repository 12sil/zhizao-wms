"""智造WMS · Streamlit 主入口。

运行：python -m streamlit run app.py
主入口仅负责导航、样式及数据空间；业务规则和 CSV 读写放在 core 中。
三大业务板块独立，基础档案维护放在辅助导航组。此包仅用于线上比赛演示。
"""
from functools import partial
import logging
import tempfile
import uuid
from pathlib import Path
import streamlit as st
from filelock import Timeout
from config import ROOT
from core.storage import StorageError
from core.session_store import SessionCsvStore
from core.demo import seed_demo, reset_demo_orders
from views import dashboard, trace, importer, orders, customers, products

st.set_page_config(page_title="智造WMS · 仓储库存与智能补货预警系统", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
st.markdown("<style>" + (ROOT / "assets/style.css").read_text(encoding="utf-8-sig") + "</style>", unsafe_allow_html=True)
st.markdown('<div class="brand-banner">智造WMS | 仓储库存与智能补货预警系统</div>', unsafe_allow_html=True)
with st.sidebar:
    st.markdown("# 📚 智造WMS")
    st.caption("仓储库存 · 物料与出入库管理")
    # 线上包固定为演示模式，不提供进入真实业务空间的入口。
    demo = True
    st.caption("仓库 / 部门与物料管理")
    st.divider()
try:
    # 每个浏览器会话使用独立演示目录，避免评委互相修改同一份样例。
    if "demo_session" not in st.session_state:
        st.session_state.demo_session = uuid.uuid4().hex
    demo_root = Path(tempfile.gettempdir()) / "wms_sessions" / st.session_state.demo_session
    with st.spinner("加载中..."):
        store = SessionCsvStore(demo_root)
        if demo:
            seed_demo(store)
    with st.sidebar:
        # 仅覆盖当前浏览器会话的演示出入库流水，不影响其他访客和仓库/部门/物料档案。
        st.caption("快速填充一组示例出入库流水")
        if st.button("一键加载演示数据", key="load_demo", use_container_width=True):
            reset_demo_orders(store)
            st.success("已加载 5 条演示出入库流水。")
except (StorageError, OSError, Timeout) as exc:
    st.error(f"无法打开数据目录：{exc}")
    st.stop()

# Streamlit 原生多页导航：每个页面一个 render 函数，便于单独修改和测试。
pages = {
    "仓储库存核心模块": [
        st.Page(partial(trace.render, store), title="① 双向数据查询", icon="🔎", url_path="trace"),
        st.Page(partial(dashboard.render, store), title="② 智能补货预警", icon="📊", url_path="dashboard", default=True),
        st.Page(partial(importer.render, store), title="③ 出入库单据识别", icon="✨", url_path="import"),
    ],
    "基础资料与业务维护": [
        st.Page(partial(orders.render, store), title="手动出入库流水", icon="📝", url_path="orders"),
        st.Page(partial(customers.render, store), title="仓库/部门档案", icon="👥", url_path="customers"),
        st.Page(partial(products.render, store), title="物料资料库", icon="📚", url_path="products"),
    ],
}
page = st.navigation(pages)
with st.sidebar:
    st.divider()
    st.caption("安全库存阈值：10,000")
    st.markdown('<div class="core-formula">💡 核心逻辑：库存低于 10,000 时触发紧急补货预警</div>', unsafe_allow_html=True)
try:
    page.run()
except (StorageError, OSError, Timeout) as exc:
    logging.exception("数据操作失败")
    st.error(f"数据暂时不可用：{exc}。已有快照不会被覆盖，请检查磁盘和文件占用后重试。")


