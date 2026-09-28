"""CSV 永久存储层：多表快照 + 文件锁 + 原子切换。

为什么不直接分别覆盖三个 CSV：程序在第二个 CSV 写到一半断电时，
可能出现出入库流水已经存在、仓库/部门却尚未保存的问题。
本实现先完整写入新一代 CSV，再原子替换 CURRENT 指针。
每代都保留，既避免半写数据，也天然保留历史备份。
业务数据全部是标准 UTF-8 BOM CSV，Excel 可以直接打开。
"""
from contextlib import contextmanager
from pathlib import Path
from copy import deepcopy
import csv
import io
import os
import re
import uuid
import zipfile
from filelock import FileLock

SCHEMAS = {
    "customers": ["id", "name", "contact", "phone", "address", "notes", "created_at"],
    "products": ["id", "code", "name", "unit", "description", "specs", "checklist", "bom", "image_path", "current_stock", "created_at"],
    "orders": ["id", "customer_id", "product_id", "customer_name", "product_name", "product_code", "unit", "quantity", "order_month", "delivery_deadline", "ship_due_date", "status", "shipped_date", "delivered_date", "source", "source_file", "import_key", "notes", "created_at", "updated_at"],
    "history": ["id", "order_id", "from_status", "to_status", "shipped_date", "delivered_date", "note", "created_at"],
    "imports": ["id", "file_hash", "file_name", "engine", "order_ids", "raw_text", "created_at"],
}


class StorageError(RuntimeError):
    """可在页面上明确展示的存储错误；绝不通过清空文件“修复”错误。"""


class CsvStore:
    """同一台机器的多会话写入串行化；每次读取拿到一致的完整快照。"""
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.generations = self.root / "generations"
        self.generations.mkdir(exist_ok=True)
        self.lock = FileLock(str(self.root / ".write.lock"), timeout=15)
        with self.lock:
            if not (self.root / "CURRENT").exists():
                if any(self.generations.iterdir()):
                    raise StorageError("CURRENT 指针缺失，但历史数据仍存在。请依据说明恢复，系统不会自动清空数据。")
                self._commit({table: [] for table in SCHEMAS})

    def current_path(self):
        """只接受程序生成的代号，避免数据指针访问项目外目录。"""
        generation = (self.root / "CURRENT").read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{32}", generation):
            raise StorageError("数据版本指针无效，请从历史备份恢复。")
        return self.generations / generation

    def _read(self):
        result = {}
        for table, columns in SCHEMAS.items():
            path = self.current_path() / f"{table}.csv"
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    if reader.fieldnames != columns:
                        raise StorageError(f"{table}.csv 的表头被修改，停止读写以保护原数据。")
                    result[table] = list(reader)
                    if any(None in row or any(v is None for v in row.values()) for row in result[table]):
                        raise StorageError(f"{table}.csv 存在不完整数据行。")
            except (OSError, UnicodeError, csv.Error) as exc:
                raise StorageError(f"无法读取 {table}.csv：{exc}") from exc
        return result

    def read(self):
        with self.lock:
            return deepcopy(self._read())

    def _commit(self, tables):
        generation = uuid.uuid4().hex
        folder = self.generations / generation
        folder.mkdir()
        # flush + fsync 确保数据先落盘；旧快照永远不被覆盖。
        for name, fields in SCHEMAS.items():
            with (folder / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="raise")
                writer.writeheader()
                writer.writerows(tables[name])
                f.flush()
                os.fsync(f.fileno())
        pointer = self.root / f".current-{generation}.tmp"
        with pointer.open("w", encoding="utf-8") as f:
            f.write(generation)
            f.flush()
            os.fsync(f.fileno())
        os.replace(pointer, self.root / "CURRENT")

    @contextmanager
    def transaction(self):
        """在锁内完成读-校验-写；业务异常会直接退出，不提交任何表。"""
        with self.lock:
            tables = self._read()
            before = deepcopy(tables)
            yield tables
            if tables != before:
                self._commit(tables)

    def export_zip(self):
        """只导出当前一致快照及附件；不把 API 密钥写入备份。"""
        output = io.BytesIO()
        with self.lock, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
            for name in SCHEMAS:
                z.write(self.current_path() / f"{name}.csv", f"{name}.csv")
            assets = self.root / "uploads"
            if assets.exists():
                for path in assets.rglob("*"):
                    if path.is_file():
                        z.write(path, str(path.relative_to(self.root)))
        return output.getvalue()



