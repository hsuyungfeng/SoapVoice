"""
病例範本 RAG 系統

使用 Chroma 向量資料庫與 sentence-transformers 實現病例範本的語義檢索功能。
支援 .txt 和 .docx 檔案的讀取、分塊、向量化，以及語義搜尋。
"""

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

import numpy as np

# 依賴檢查
try:
    import chromadb
except ImportError:
    raise ImportError("請安裝 chromadb: uv add chromadb")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError("請安裝 sentence-transformers: uv add sentence-transformers")

try:
    from docx import Document
except ImportError:
    raise ImportError("請安裝 python-docx: uv add python-docx")

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 預設配置
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_COLLECTION_NAME = "case_templates"


class TextChunker:
    """文字分塊器"""

    def __init__(
        self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    ):
        """初始化分塊器

        Args:
            chunk_size: 分塊大小（字元數）
            chunk_overlap: 重疊大小（字元數）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, source_file: str, source_name: str) -> list[dict[str, Any]]:
        """將文字分塊

        Args:
            text: 要分塊的文字
            source_file: 來源檔案路徑
            source_name: 來源檔案名稱

        Returns:
            分塊後的文字區塊列表，每個區塊包含 text、source_file、source_name、chunk_index
        """
        if not text or len(text.strip()) < 10:
            logger.warning(f"文字內容太短，無法分塊: {source_file}")
            return []

        chunks = []
        start = 0
        text_length = len(text)
        chunk_index = 0

        while start < text_length:
            end = start + self.chunk_size
            chunk_text = text[start:end]

            # 移除過短的區塊
            if len(chunk_text.strip()) >= 20:
                chunks.append(
                    {
                        "text": chunk_text.strip(),
                        "source_file": source_file,
                        "source_name": source_name,
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1

            start += self.chunk_size - self.chunk_overlap

        logger.debug(f"從 {source_name} 產生 {len(chunks)} 個區塊")
        return chunks


class FileReader:
    """檔案讀取器"""

    @staticmethod
    def read_file(file_path: Path) -> Optional[str]:
        """讀取檔案內容

        Args:
            file_path: 檔案路徑

        Returns:
            檔案內容，失敗返回 None
        """
        try:
            ext = file_path.suffix.lower()

            if ext == ".txt":
                return FileReader._read_txt(file_path)
            elif ext == ".docx":
                return FileReader._read_docx(file_path)
            else:
                logger.warning(f"不支援的檔案格式: {ext} - {file_path}")
                return None

        except Exception as e:
            logger.error(f"讀取檔案失敗 {file_path}: {e}")
            return None

    @staticmethod
    def _read_txt(file_path: Path) -> Optional[str]:
        """讀取文字檔"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if content and len(content.strip()) > 10:
                    return content
                logger.warning(f"文字檔案內容太短或為空: {file_path}")
                return None
        except Exception as e:
            logger.error(f"讀取文字檔失敗 {file_path}: {e}")
            return None

    @staticmethod
    def _read_docx(file_path: Path) -> Optional[str]:
        """讀取 Word 文件"""
        try:
            doc = Document(file_path)
            paragraphs = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    paragraphs.append(paragraph.text)
            result = "\n".join(paragraphs)
            if result and len(result.strip()) > 10:
                return result
            logger.warning(f".docx 檔案內容太短: {file_path}")
            return None
        except Exception as e:
            logger.error(f"讀取 .docx 檔案失敗 {file_path}: {e}")
            return None


class CaseTemplateRAG:
    """病例範本 RAG 系統"""

    def __init__(
        self,
        data_dir: Path,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ):
        """初始化 RAG 系統

        Args:
            data_dir: 資料儲存目錄
            embedding_model: 嵌入模型名稱
            collection_name: Chroma 集合名稱
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.chroma_dir = self.data_dir / "chroma"
        self.sqlite_path = self.data_dir / "case_templates.db"
        self.collection_name = collection_name

        # 初始化嵌入模型
        logger.info(f"載入嵌入模型: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)

        # 初始化 Chroma
        self.chroma_client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "病例範本向量資料庫"},
        )

        # 初始化分塊器
        self.chunker = TextChunker()

        logger.info("RAG 系統初始化完成")
        logger.info(f"Chroma 目錄: {self.chroma_dir}")
        logger.info(f"SQLite 路徑: {self.sqlite_path}")
        logger.info(f"集合名稱: {self.collection_name}")

    def load_templates(
        self,
        template_dir: Path,
        file_extensions: list[str] = None,
        clear_existing: bool = False,
    ) -> int:
        """載入病例範本檔案

        Args:
            template_dir: 病例範本目錄路徑
            file_extensions: 要處理的檔案副檔名列表
            clear_existing: 是否清除現有資料

        Returns:
            載入的區塊數量
        """
        if file_extensions is None:
            file_extensions = [".txt", ".docx"]

        if not template_dir.exists():
            logger.error(f"病例範本目錄不存在: {template_dir}")
            return 0

        # 清除現有資料
        if clear_existing:
            logger.info("清除現有向量資料")
            try:
                # 嘗試取得所有 ID 並刪除
                existing_ids = self.collection.get().get("ids", [])
                if existing_ids:
                    self.collection.delete(ids=existing_ids)
            except Exception as e:
                logger.warning(f"清除向量資料時發生錯誤: {e}")
                # 嘗試刪除整個集合並重新創建
                try:
                    self.chroma_client.delete_collection(name=self.collection_name)
                    self.collection = self.chroma_client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={"description": "病例範本向量資料庫"},
                    )
                except Exception as e2:
                    logger.error(f"重新創建集合失敗: {e2}")

            if self.sqlite_path.exists():
                self.sqlite_path.unlink()

        # 收集所有檔案
        template_files = []
        for ext in file_extensions:
            files = list(template_dir.rglob(f"*{ext}"))
            template_files.extend(files)

        logger.info(f"找到 {len(template_files)} 個病例範本檔案")

        if not template_files:
            logger.warning("未找到任何病例範本檔案")
            return 0

        # 處理每個檔案
        total_chunks = 0
        documents = []
        embeddings = []
        metadatas = []
        ids = []

        for file_path in template_files:
            content = FileReader.read_file(file_path)
            if not content:
                continue

            # 分塊
            chunks = self.chunker.chunk_text(content, str(file_path), file_path.name)
            if not chunks:
                continue

            # 生成嵌入向量
            chunk_texts = [chunk["text"] for chunk in chunks]
            try:
                chunk_embeddings = self.embedding_model.encode(chunk_texts, show_progress_bar=False)
            except Exception as e:
                logger.error(f"生成嵌入向量失敗 {file_path}: {e}")
                continue

            # 添加到批次
            for i, chunk in enumerate(chunks):
                doc_id = f"{file_path.name}_{i}"
                documents.append(chunk["text"])
                embeddings.append(chunk_embeddings[i].tolist())
                metadatas.append(
                    {
                        "source_file": chunk["source_file"],
                        "source_name": chunk["source_name"],
                        "chunk_index": chunk["chunk_index"],
                    }
                )
                ids.append(doc_id)

            total_chunks += len(chunks)
            logger.info(f"已處理: {file_path.name} ({len(chunks)} 個區塊)")

        if not documents:
            logger.warning("沒有可用的文件區塊")
            return 0

        # 批次添加到 Chroma
        logger.info(f"正在將 {len(documents)} 個區塊添加到向量資料庫...")
        try:
            self.collection.add(
                documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids
            )
            logger.info("向量資料庫更新完成")
        except Exception as e:
            logger.error(f"添加到向量資料庫失敗: {e}")
            return 0

        # 同步到 SQLite
        self._sync_to_sqlite(documents, metadatas, ids)

        logger.info(f"病例範本載入完成，共 {total_chunks} 個區塊")
        return total_chunks

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """語義搜尋

        Args:
            query: 搜尋查詢
            top_k: 回傳結果數量
            min_score: 最低相似度分數

        Returns:
            搜尋結果列表
        """
        if not query or len(query.strip()) < 2:
            logger.warning("查詢字串太短")
            return []

        logger.info(f"搜尋: {query}")

        # 生成查詢嵌入向量
        try:
            query_embedding = self.embedding_model.encode([query], show_progress_bar=False)[
                0
            ].tolist()
        except Exception as e:
            logger.error(f"生成查詢嵌入向量失敗: {e}")
            return []

        # 搜尋 Chroma
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"搜尋失敗: {e}")
            return []

        # 處理結果
        search_results = []
        if results["documents"] and len(results["documents"]) > 0:
            for i in range(len(results["documents"][0])):
                distance = results["distances"][0][i]
                # 轉換距離為相似度分數 (距離越小，相似度越高)
                score = 1.0 / (1.0 + distance)

                if score >= min_score:
                    search_results.append(
                        {
                            "text": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "score": score,
                            "distance": distance,
                        }
                    )

        logger.info(f"找到 {len(search_results)} 個相關結果")
        return search_results

    def get_stats(self) -> dict[str, Any]:
        """取得統計資訊

        Returns:
            統計資訊字典
        """
        try:
            count = self.collection.count()
        except Exception as e:
            logger.error(f"取得 Chroma 統計失敗: {e}")
            count = 0

        # SQLite 統計
        sqlite_count = 0
        if self.sqlite_path.exists():
            try:
                conn = sqlite3.connect(str(self.sqlite_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM chunks")
                sqlite_count = cursor.fetchone()[0] or 0
                conn.close()
            except Exception as e:
                logger.warning(f"取得 SQLite 統計失敗: {e}")

        return {
            "chroma_count": count,
            "sqlite_count": sqlite_count,
            "collection_name": self.collection_name,
            "chroma_path": str(self.chroma_dir),
            "sqlite_path": str(self.sqlite_path),
        }

    def export_to_sqlite(self) -> bool:
        """將 Chroma 資料匯出到 SQLite

        Returns:
            是否成功
        """
        logger.info("開始匯出到 SQLite...")

        try:
            # 取得所有資料
            all_data = self.collection.get(include=["documents", "metadatas", "embeddings"])

            if not all_data or not all_data.get("ids"):
                logger.warning("Chroma 中沒有資料可匯出")
                return False

            # 建立 SQLite 資料表
            conn = sqlite3.connect(str(self.sqlite_path))
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    source_file TEXT,
                    source_name TEXT,
                    chunk_index INTEGER,
                    embedding BLOB
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_file ON chunks(source_file)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_name ON chunks(source_name)")

            # 插入資料
            for i in range(len(all_data["ids"])):
                embeddings_list = all_data.get("embeddings")
                embedding_bytes = None
                if (
                    embeddings_list is not None
                    and i < len(embeddings_list)
                    and embeddings_list[i] is not None
                ):
                    embedding_arr = np.array(embeddings_list[i])
                    if embedding_arr.size > 0:
                        embedding_bytes = embedding_arr.astype(np.float32).tobytes()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO chunks 
                    (id, document, source_file, source_name, chunk_index, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        all_data["ids"][i],
                        all_data["documents"][i],
                        all_data["metadatas"][i].get("source_file", ""),
                        all_data["metadatas"][i].get("source_name", ""),
                        all_data["metadatas"][i].get("chunk_index", 0),
                        embedding_bytes,
                    ),
                )

            conn.commit()
            conn.close()

            logger.info(f"匯出完成: {len(all_data['ids'])} 筆資料")
            return True

        except Exception as e:
            logger.error(f"匯出到 SQLite 失敗: {e}")
            return False

    def _sync_to_sqlite(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """同步資料到 SQLite（增量更新）"""
        if not self.sqlite_path.exists():
            self.export_to_sqlite()
            return

        try:
            conn = sqlite3.connect(str(self.sqlite_path))
            cursor = conn.cursor()

            for i in range(len(ids)):
                # 檢查是否已存在
                cursor.execute("SELECT id FROM chunks WHERE id = ?", (ids[i],))
                if cursor.fetchone():
                    continue

                cursor.execute(
                    """
                    INSERT INTO chunks (id, document, source_file, source_name, chunk_index, embedding)
                    VALUES (?, ?, ?, ?, ?, NULL)
                """,
                    (
                        ids[i],
                        documents[i],
                        metadatas[i].get("source_file", ""),
                        metadatas[i].get("source_name", ""),
                        metadatas[i].get("chunk_index", 0),
                    ),
                )

            conn.commit()
            conn.close()
            logger.debug("SQLite 同步完成")
        except Exception as e:
            logger.warning(f"SQLite 同步失敗: {e}")


def setup_logging(verbose: bool = False) -> None:
    """設定日誌等級"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description="病例範本 RAG 系統")

    # 全域參數
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="顯示詳細日誌",
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化並載入病例範本")
    init_parser.add_argument(
        "--template-dir",
        type=Path,
        required=True,
        help="病例範本目錄路徑",
    )
    init_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/rag"),
        help="向量資料儲存目錄",
    )
    init_parser.add_argument(
        "--clear",
        action="store_true",
        help="清除現有資料後重新載入",
    )
    init_parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt", ".docx"],
        help="要處理的檔案副檔名",
    )

    # search 命令
    search_parser = subparsers.add_parser("search", help="語義搜尋病例範本")
    search_parser.add_argument(
        "--query",
        "-q",
        type=str,
        required=True,
        help="搜尋查詢",
    )
    search_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/rag"),
        help="向量資料儲存目錄",
    )
    search_parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=5,
        help="回傳結果數量",
    )
    search_parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="最低相似度分數",
    )

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="顯示統計資訊")
    stats_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/rag"),
        help="向量資料儲存目錄",
    )

    # export 命令
    export_parser = subparsers.add_parser("export", help="匯出向量資料庫到 SQLite")
    export_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/rag"),
        help="向量資料儲存目錄",
    )

    args = parser.parse_args()

    # 設定日誌
    setup_logging(args.verbose if hasattr(args, "verbose") else False)

    # 解析子命令
    if hasattr(args, "command"):
        command = args.command
    else:
        parser.print_help()
        return

    # 根據命令執行
    if command == "init":
        data_dir = Path(args.data_dir)
        if not data_dir.is_absolute():
            # 使用專案根目錄
            base_dir = Path(__file__).parent.parent.parent
            data_dir = base_dir / data_dir

        template_dir = args.template_dir
        if not template_dir.is_absolute():
            base_dir = Path(__file__).parent.parent.parent
            template_dir = base_dir / template_dir

        logger.info("=" * 60)
        logger.info("初始化病例範本 RAG 系統")
        logger.info(f"資料目錄: {data_dir}")
        logger.info(f"範本目錄: {template_dir}")
        logger.info("=" * 60)

        rag = CaseTemplateRAG(data_dir=data_dir)
        count = rag.load_templates(
            template_dir=template_dir,
            file_extensions=args.extensions,
            clear_existing=args.clear,
        )

        logger.info("=" * 60)
        logger.info(f"初始化完成，共載入 {count} 個區塊")
        logger.info("=" * 60)

    elif command == "search":
        data_dir = Path(args.data_dir)
        if not data_dir.is_absolute():
            base_dir = Path(__file__).parent.parent.parent
            data_dir = base_dir / data_dir

        logger.info("=" * 60)
        logger.info("病例範本語義搜尋")
        logger.info(f"查詢: {args.query}")
        logger.info("=" * 60)

        rag = CaseTemplateRAG(data_dir=data_dir)
        results = rag.search(
            query=args.query,
            top_k=args.top_k,
            min_score=args.min_score,
        )

        logger.info("=" * 60)
        if results:
            for i, result in enumerate(results, 1):
                logger.info(f"\n--- 結果 {i} (相似度: {result['score']:.4f}) ---")
                logger.info(f"來源: {result['metadata'].get('source_name', 'unknown')}")
                logger.info(f"內容: {result['text'][:200]}...")
        else:
            logger.info("未找到相關結果")
        logger.info("=" * 60)

    elif command == "stats":
        data_dir = Path(args.data_dir)
        if not data_dir.is_absolute():
            base_dir = Path(__file__).parent.parent.parent
            data_dir = base_dir / data_dir

        logger.info("=" * 60)
        logger.info("病例範本 RAG 統計資訊")
        logger.info("=" * 60)

        rag = CaseTemplateRAG(data_dir=data_dir)
        stats = rag.get_stats()

        logger.info(f"集合名稱: {stats['collection_name']}")
        logger.info(f"Chroma 區塊數: {stats['chroma_count']}")
        logger.info(f"SQLite 區塊數: {stats['sqlite_count']}")
        logger.info(f"Chroma 路徑: {stats['chroma_path']}")
        logger.info(f"SQLite 路徑: {stats['sqlite_path']}")
        logger.info("=" * 60)

    elif command == "export":
        data_dir = Path(args.data_dir)
        if not data_dir.is_absolute():
            base_dir = Path(__file__).parent.parent.parent
            data_dir = base_dir / data_dir

        logger.info("=" * 60)
        logger.info("匯出向量資料庫到 SQLite")
        logger.info("=" * 60)

        rag = CaseTemplateRAG(data_dir=data_dir)
        success = rag.export_to_sqlite()

        if success:
            logger.info("匯出完成")
        else:
            logger.error("匯出失敗")
        logger.info("=" * 60)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
