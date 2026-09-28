"""业务常量：所有页面统一引用，避免各页面重复定义规则。"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent
# 数据路径以程序所在目录为基准，不受启动命令所在目录影响。
# 可在服务器上设置 CAMPUS_DATA_DIR 指向持久化磁盘。
DATA_DIR = Path(os.getenv("CAMPUS_DATA_DIR", str(ROOT / "data"))).resolve()
SAFETY_STOCK = 10000
LOW_STOCK = 15000
MAX_FILE_MB = 20
MAX_PDF_PAGES = 12
STATUSES = ("入库", "出库", "已取消")



