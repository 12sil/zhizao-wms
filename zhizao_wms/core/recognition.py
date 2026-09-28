"""出入库流水文件识别：真实本地 OCR 与可选视觉大模型，两条路径共用校验器。

本地：RapidOCR 神经网络识字 + 可解释规则提取。适用于字段标签清楚的出入库流水。
云端：OpenAI Responses 视觉接口 + 严格 JSON Schema。适用于复杂表格、多物料。
本地无法确定的字段保持空值，绝不生成假识别结果；云端也必须通过同样的业务校验。
"""
from functools import lru_cache
from pathlib import Path
import base64
import hashlib
import io
import json
import re
import urllib.error
import urllib.request
from threading import Lock

# 免费服务器上的多个识别请求串行执行，避免共享模型状态竞争。
_OCR_LOCK = Lock()
from PIL import Image, ImageOps
from config import MAX_FILE_MB, MAX_PDF_PAGES
from core.rules import quantity_text

DATE_RE = r"(20\d{2})\s*[年/\.\-]\s*(\d{1,2})\s*[月/\.\-]\s*(\d{1,2})\s*日?"
FIELDS = ("customer_name", "product_name", "product_code", "quantity", "unit")


def normalized_date(text):
    """兼容中文和数字日期，拒绝不完整年份、无效日期。"""
    m = re.search(DATE_RE, str(text))
    if not m:
        return ""
    try:
        return parse_date(f"{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}").isoformat()
    except ValueError:
        return ""


def file_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_file(raw, filename):
    suffix = Path(filename).suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".pdf"):
        raise ValueError("仅支持 PNG、JPG、WebP 和 PDF。")
    if not raw or len(raw) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"文件为空或超过 {MAX_FILE_MB} MB。")
    if suffix == ".pdf" and not raw.startswith(b"%PDF"):
        raise ValueError("文件内容不是有效 PDF。")
    return suffix


def image_bytes(raw):
    """统一纠正 EXIF 方向并限制像素，用于 OCR/云端输入。"""
    try:
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > 30000000:
            raise ValueError("图片超过 3000 万像素，请先压缩。")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((2600, 2600))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except (OSError, Image.DecompressionBombError):
        raise ValueError("图片内容损坏或格式不支持。") from None


def pdf_images(raw):
    """用 PDFium 渲染每页，扫描 PDF 与普通 PDF 都支持，不依赖系统安装 Poppler。"""
    import pypdfium2 as pdfium
    try:
        document = pdfium.PdfDocument(raw)
    except Exception as exc:
        raise ValueError("PDF 无法打开，可能已加密或损坏。") from exc
    try:
        if len(document) > MAX_PDF_PAGES:
            raise ValueError(f"单次最多识别 {MAX_PDF_PAGES} 页，请拆分后上传。")
        result = []
        for page in document:
            scale = min(2.0, 2600 / max(page.get_size()))
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            result.append(buf.getvalue())
            bitmap.close()
            page.close()
        return result
    finally:
        document.close()


@lru_cache(maxsize=1)
def get_ocr():
    """模型只加载一次；RapidOCR 安装包内置模型，识别时无需联网。"""
    try:
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)
    except Exception as exc:
        # 云端可能是动态库、Python 版本或推理后端加载失败；保留真实原因，避免误报“未安装”。
        detail = str(exc).strip().replace("\n", " ")[:240] or exc.__class__.__name__
        raise ValueError(f"OCR 引擎启动失败（{exc.__class__.__name__}）：{detail}。请查看部署日志。") from exc


def ocr_image(raw):
    """按纵坐标聚合同一行的文本框，再按横坐标排序，保留表格列顺序。"""
    import numpy as np
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    with _OCR_LOCK:
        result, _ = get_ocr()(np.asarray(image))
    if not result:
        return "", 0.0
    boxes = []
    for box, text, score in result:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        boxes.append((sum(ys) / 4, min(xs), max(ys) - min(ys), text, float(score)))
    lines = []
    for item in sorted(boxes):
        if lines and abs(lines[-1][0][0] - item[0]) < max(8, item[2] * .55):
            lines[-1].append(item)
        else:
            lines.append([item])
    text = "\n".join("  ".join(x[3] for x in sorted(line, key=lambda x: x[1])) for line in lines)
    return text, min(x[4] for x in boxes)


def _label(text, pattern):
    # 只抓明确标注的字段，避免把供应商、联系电话、单价当成仓库/部门或数量。
    m = re.search(rf"(?:{pattern})\s*[:：]\s*([^\n]+)", text)
    return m.group(1).strip() if m else ""


def parse_local(text):
    """解析标准字段及常见简洁表格；复杂排版交由人工校对或视觉模型。

    不把识别范围扩张为任意文本中的第一个日期/数字，这是出入库流水识别中最危险的误匹配。
    """
    text = text.replace("：", ":")
    customer = _label(text, r"仓库/部门名称|仓库/部门|购货单位|分配单位|需方")
    customer = re.split(r"\s{2,}|(?:负责人|电话|出入库流水号)\s*:", customer)[0].strip()
    global_date = normalized_date(_label(text, r"流水日期|流水日期|流水日期|流水日期|交货日期|交期|截止日期|流水日期"))
    positions = list(re.finditer(r"(?:物料名称|物料|品名)\s*:\s*", text))
    rows = []
    for i, pos in enumerate(positions):
        block = text[pos.start(): positions[i + 1].start() if i + 1 < len(positions) else len(text)]
        product = _label(block, r"物料名称|物料|品名")
        product = re.split(r"\s{2,}|(?:数量|物料编码|编码|规格)\s*:", product)[0].strip()
        quantity = _label(block, r"出入库流水数量|分配数量|数量")
        qm = re.match(r"([0-9][0-9,]*(?:\.\d{1,3})?)\s*(件|套|个|台|米|千克|公斤|箱|包|kg|KG)?", quantity)
        rows.append({"customer_name": customer, "product_name": product,
                     "product_code": _label(block, r"物料编码|编码|料号").split("  ")[0],
                     "quantity": qm[1].replace(",", "") if qm else "",
                     "unit": (qm[2] if qm and qm[2] else _label(block, r"计量单位|单位")) or "件",
                     "delivery_deadline": normalized_date(_label(block, r"流水日期|流水日期|流水日期|流水日期|交货日期|交期|截止日期|流水日期")) or global_date})
    # 支持：物料名称 数量 单位 流水日期；不猜测带价格金额等额外数字的复杂表格。
    if not rows:
        for line in text.splitlines():
            m = re.match(r"^\s*(.+?)\s{2,}([\d,]+(?:\.\d{1,3})?)\s*(件|套|个|台|米|千克|公斤|箱|包|kg)?\s{2,}(20\d{2}[^\n]+)$", line)
            if m and normalized_date(m[4]):
                rows.append({"customer_name": customer, "product_name": m[1].strip(), "product_code": "", "quantity": m[2].replace(",", ""), "unit": m[3] or "件", "delivery_deadline": normalized_date(m[4])})
    if not rows:
        rows = [{"customer_name": customer, "product_name": "", "product_code": "", "quantity": "", "unit": "件", "delivery_deadline": global_date}]
    return rows


def validation_errors(rows):
    errors = []
    if not rows: return ["未识别到出入库流水行。"]
    for i, row in enumerate(rows, 1):
        for field, label in (("customer_name", "仓库/部门名称"), ("product_name", "物料名称")):
            if not str(row.get(field, "")).strip(): errors.append(f"第 {i} 行缺少{label}。")
        try: quantity_text(row.get("quantity", ""))
        except ValueError as exc: errors.append(f"第 {i} 行：{exc}")
    return errors

def recognize_local(raw, filename):
    suffix = validate_file(raw, filename)
    confidence = 1.0
    if suffix == ".pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise ValueError("请上传未加密 PDF。")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError(f"单次最多识别 {MAX_PDF_PAGES} 页。")
            texts = [(p.extract_text() or "").strip() for p in reader.pages]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("PDF 文本解析失败，请检查文件。") from exc
        # 混合 PDF 逐页处理，不能因首页有文本就忽略后面的扫描页。
        rendered = None
        for i, text in enumerate(texts):
            if len(text) < 20:
                rendered = rendered or pdf_images(raw)
                texts[i], score = ocr_image(rendered[i])
                confidence = min(confidence, score)
        text = "\n\n".join(texts)
    else:
        text, confidence = ocr_image(image_bytes(raw))
    rows = parse_local(text)
    issues = validation_errors(rows)
    if confidence < .85:
        issues.append("存在低清晰度文字，请核对识别结果后再入库。")
    # 不把多个仓库/部门文件默默归入第一个仓库/部门。
    customers = re.findall(r"(?:仓库/部门名称|仓库|部门|购货单位|分配单位|需方)\s*[:：]\s*([^\n]+)", text)
    if len(set(customers)) > 1:
        issues.append("文件包含多个仓库/部门，请拆分文件或使用视觉大模型逐行识别。")
    return {"rows": rows, "raw_text": text, "issues": issues, "engine": "本地 OCR", "ocr_score": confidence}






