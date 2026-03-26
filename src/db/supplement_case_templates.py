"""
病例範本補充腳本

將 CurrentData/各种病例规范模板/ 目錄中的病例範本補充到資料庫中
支援 .txt, .doc, .docx 檔案格式
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Optional
import sys
import os

# 嘗試導入 docx 處理模組
try:
    from docx import Document

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("警告: python-docx 未安裝，無法處理 .docx 檔案")

logger = logging.getLogger(__name__)


class CaseTemplateSupplementer:
    """病例範本補充器"""

    def __init__(self, db_path: Path, template_dir: Path):
        """初始化

        Args:
            db_path: SQLite 資料庫路徑
            template_dir: 病例範本目錄路徑
        """
        self.db_path = db_path
        self.template_dir = template_dir
        self.supported_extensions = [".txt"]

        if HAS_DOCX:
            self.supported_extensions.extend([".docx", ".doc"])

    def supplement(self, overwrite: bool = False) -> None:
        """補充病例範本

        Args:
            overwrite: 是否覆蓋已存在的範本
        """
        logger.info("=" * 60)
        logger.info("開始補充病例範本")
        logger.info("=" * 60)

        if not self.template_dir.exists():
            logger.error(f"病例範本目錄不存在: {self.template_dir}")
            return

        # 掃描所有支援的檔案
        template_files = []
        for ext in self.supported_extensions:
            files = list(self.template_dir.rglob(f"*{ext}"))
            template_files.extend(files)

        logger.info(f"找到 {len(template_files)} 個病例範本檔案")

        if not template_files:
            logger.warning("未找到任何病例範本檔案")
            return

        conn = sqlite3.connect(str(self.db_path))

        try:
            # 清空現有病例範本（如果選擇覆蓋）
            if overwrite:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM case_templates")
                conn.commit()
                logger.info("已清空現有病例範本")

            inserted_count = 0
            skipped_count = 0
            error_count = 0

            for file_path in template_files:
                try:
                    # 檢查是否已存在
                    if not overwrite:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT COUNT(*) FROM case_templates WHERE source_file = ?",
                            (str(file_path),),
                        )
                        if cursor.fetchone()[0] > 0:
                            logger.debug(f"已存在，跳過: {file_path}")
                            skipped_count += 1
                            continue

                    # 讀取檔案內容
                    content = self._read_file_content(file_path)
                    if not content:
                        logger.warning(f"檔案內容為空: {file_path}")
                        continue

                    # 從路徑提取資訊
                    relative_path = file_path.relative_to(self.template_dir)
                    parts = relative_path.parts

                    specialty = parts[0] if len(parts) > 1 else "一般"
                    category = parts[-2] if len(parts) > 2 else "病例"
                    template_name = file_path.stem

                    # 插入資料庫
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO case_templates 
                        (template_name, category, specialty, content, source_file)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (template_name, category, specialty, content, str(file_path)),
                    )

                    inserted_count += 1

                    # 每100筆提交一次
                    if inserted_count % 100 == 0:
                        conn.commit()
                        logger.info(f"進度: {inserted_count}/{len(template_files)}")

                except Exception as e:
                    error_count += 1
                    logger.error(f"處理檔案失敗 {file_path}: {e}")

            conn.commit()

            logger.info("=" * 60)
            logger.info(f"病例範本補充完成!")
            logger.info(f"成功插入: {inserted_count}")
            logger.info(f"跳過已存在: {skipped_count}")
            logger.info(f"處理失敗: {error_count}")
            logger.info("=" * 60)

            # 顯示統計資訊
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM case_templates")
            total = cursor.fetchone()[0]
            logger.info(f"資料庫中總病例範本數: {total}")

            # 顯示各專科統計
            cursor.execute("""
                SELECT specialty, COUNT(*) as count 
                FROM case_templates 
                GROUP BY specialty 
                ORDER BY count DESC
            """)
            logger.info("\n各專科病例範本數量:")
            for specialty, count in cursor.fetchall():
                logger.info(f"  {specialty}: {count} 個")

        except Exception as e:
            conn.rollback()
            logger.error(f"病例範本補充失敗: {e}")
            raise
        finally:
            conn.close()

    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """讀取檔案內容

        Args:
            file_path: 檔案路徑

        Returns:
            檔案內容字串，失敗返回 None
        """
        try:
            ext = file_path.suffix.lower()

            if ext == ".txt":
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if content and len(content.strip()) > 10:  # 至少要有一些內容
                        return content
                    else:
                        logger.warning(f"檔案內容太短或為空: {file_path}")
                        return None

            elif ext == ".docx" and HAS_DOCX:
                # 只處理 .docx 檔案，跳過 .doc
                try:
                    doc = Document(file_path)
                    content = []
                    for paragraph in doc.paragraphs:
                        if paragraph.text.strip():
                            content.append(paragraph.text)
                    result = "\n".join(content)
                    if result and len(result.strip()) > 10:
                        return result
                    else:
                        logger.warning(f".docx 檔案內容太短: {file_path}")
                        return None
                except Exception as e:
                    logger.warning(f"無法讀取 .docx 檔案 {file_path}: {e}")
                    return None

            else:
                # 跳過 .doc 和其他格式
                logger.debug(f"跳過不支援的檔案格式: {ext} - {file_path}")
                return None

        except Exception as e:
            logger.warning(f"讀取檔案失敗 {file_path}: {e}")
            return None

        except Exception as e:
            logger.error(f"讀取檔案失敗 {file_path}: {e}")
            return None

    def list_templates(self) -> None:
        """列出所有可用的病例範本"""
        if not self.template_dir.exists():
            logger.error(f"病例範本目錄不存在: {self.template_dir}")
            return

        logger.info("=" * 60)
        logger.info("可用的病例範本檔案:")
        logger.info("=" * 60)

        for ext in self.supported_extensions:
            files = list(self.template_dir.rglob(f"*{ext}"))
            if files:
                logger.info(f"\n{ext.upper()} 檔案 ({len(files)} 個):")
                for file_path in sorted(files)[:20]:  # 只顯示前20個
                    relative_path = file_path.relative_to(self.template_dir)
                    size = file_path.stat().st_size
                    logger.info(f"  {relative_path} ({size:,} bytes)")

                if len(files) > 20:
                    logger.info(f"  ... 還有 {len(files) - 20} 個檔案")


def main():
    """主程式"""
    # 設定日誌
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 設定路徑
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / "data" / "local_db" / "medical.db"
    template_dir = base_dir / "CurrentData" / "各种病例规范模板"

    # 檢查路徑
    if not db_path.exists():
        logger.error(f"資料庫不存在: {db_path}")
        sys.exit(1)

    if not template_dir.exists():
        logger.error(f"病例範本目錄不存在: {template_dir}")
        sys.exit(1)

    # 創建補充器
    supplementer = CaseTemplateSupplementer(db_path, template_dir)

    # 解析命令列參數
    import argparse

    parser = argparse.ArgumentParser(description="補充病例範本到資料庫")
    parser.add_argument("--list", action="store_true", help="列出可用的病例範本檔案")
    parser.add_argument("--overwrite", action="store_true", help="覆蓋已存在的範本")
    parser.add_argument("--dry-run", action="store_true", help="僅顯示統計，不實際插入")

    args = parser.parse_args()

    if args.list:
        supplementer.list_templates()
    elif args.dry_run:
        logger.info("乾跑模式 - 僅顯示統計")
        # 這裡可以添加乾跑邏輯
        supplementer.list_templates()
    else:
        supplementer.supplement(overwrite=args.overwrite)


if __name__ == "__main__":
    main()
