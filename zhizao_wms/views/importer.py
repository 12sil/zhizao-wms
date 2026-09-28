import pandas as pd
import streamlit as st
from core.recognition import recognize_local, file_hash, validation_errors, FIELDS
from core.service import import_orders
from views.common import header
LABELS={"customer_name":"仓库/部门名称","product_name":"物料名称","product_code":"物料编码（可选）","quantity":"数量","unit":"单位"}
def render(store):
    header("03 / DOCUMENT OCR","出入库单据智能识别","上传出入库单据识别，自动提取仓库/部门、物料和数量。"); st.markdown('<div class="flow">01 上传单据 → 02 OCR识别 → 03 核对字段 → 04 写入流水</div>',unsafe_allow_html=True)
    uploaded=st.file_uploader("上传出入库单据识别",type=["png","jpg","jpeg","webp","pdf"],help="单文件不超过 20MB，PDF 最多 12 页。")
    if uploaded is None: st.info("上传清晰的出入库单据图片或 PDF，即可自动识别。"); return
    raw=uploaded.getvalue(); digest=file_hash(raw); key="wms-recognition:"+str(store.root)+":"+digest; existing=next((x for x in store.read()["imports"] if x["file_hash"]==digest),None)
    if existing: st.success(f"该单据已入库，关联流水：{existing['order_ids']}。"); return
    if st.button("开始识别",type="primary",use_container_width=True):
        try: st.session_state[key]=recognize_local(raw,uploaded.name)
        except (ValueError,RuntimeError,OSError) as exc: st.error(str(exc))
    result=st.session_state.get(key)
    if not result:return
    if result["issues"]: st.warning("识别结果需要人工核对后入库："+"；".join(result["issues"]))
    frame=pd.DataFrame([{k:r.get(k,"") for k in FIELDS} for r in result["rows"]]); edited=st.data_editor(frame,column_config={k:st.column_config.TextColumn(v) for k,v in LABELS.items()},hide_index=True,num_rows="dynamic",use_container_width=True,key="editor:"+key)
    confirmed=st.checkbox("已核对仓库/部门、物料、数量和单位",key="confirm:"+key)
    if st.button("确认并写入出入库流水",disabled=not confirmed,type="primary"):
        try:
            rows=edited.fillna("").to_dict("records"); errors=validation_errors(rows)
            if errors: raise ValueError("；".join(errors))
            ids=import_orders(store,rows,digest,uploaded.name,raw,result["engine"],result["raw_text"]); st.success(f"已保存 {len(ids)} 条出入库流水。")
        except (ValueError,OSError) as exc: st.error(str(exc))


