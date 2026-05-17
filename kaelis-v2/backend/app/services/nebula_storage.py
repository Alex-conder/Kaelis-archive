"""
NebulaGraph 存储服务封装。

核心能力：
- 连接池生命周期管理
- nGQL 执行与结果解析
- 顶点/边的便捷 Upsert 接口
- 超时控制与连接释放
"""
import logging
import time
from contextlib import contextmanager
from typing import List, Dict, Optional, Any

from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


class NebulaStorage:
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._space = settings.NEBULA_SPACE
        self._init_pool()

    def _init_pool(self) -> None:
        """初始化连接池。失败时设置为 None，后续调用会抛出明确异常。"""
        try:
            config = NebulaConfig()
            config.max_connection_pool_size = 10
            config.timeout = 3000  # 毫秒

            self._pool = ConnectionPool()
            ok = self._pool.init(
                [(settings.NEBULA_HOST, settings.NEBULA_PORT)],
                config
            )
            if not ok:
                raise RuntimeError("ConnectionPool.init returned False")
            logger.info(
                "NebulaGraph pool ready: %s:%d",
                settings.NEBULA_HOST, settings.NEBULA_PORT
            )
        except Exception as e:
            logger.error("NebulaGraph pool init failed: %s", e)
            self._pool = None

    @contextmanager
    def session(self):
        """
        会话上下文管理器，确保连接释放。

        Yields:
            nebula3.Session: 已切换到目标 Space 的会话
        """
        if self._pool is None:
            raise RuntimeError("NebulaGraph connection pool not available")

        sess = None
        try:
            sess = self._pool.get_session(
                settings.NEBULA_USER,
                settings.NEBULA_PASSWORD
            )
            result = sess.execute(f"USE {self._space}")
            if not result.is_succeeded():
                raise RuntimeError(
                    f"USE {self._space} failed: {result.error_msg()}"
                )
            yield sess
        except Exception as e:
            logger.error("Nebula session error: %s", e)
            raise
        finally:
            if sess:
                sess.release()

    def execute(self, query: str) -> List[Dict[str, Any]]:
        """
        执行 nGQL 并返回字典列表。

        Args:
            query: nGQL 语句

        Returns:
            每行数据为一个 dict，列名为 key

        Raises:
            RuntimeError: 执行失败
        """
        with self.session() as sess:
            start = time.time()
            result = sess.execute(query)
            elapsed_ms = (time.time() - start) * 1000

            if not result.is_succeeded():
                logger.error(
                    "nGQL failed (%.1fms): %s | Query: %s",
                    elapsed_ms, result.error_msg(), query[:200]
                )
                raise RuntimeError(f"nGQL error: {result.error_msg()}")

            logger.debug("nGQL OK (%.1fms): %s", elapsed_ms, query[:200])

            columns = result.keys()
            rows: List[Dict[str, Any]] = []
            for row in result:
                record: Dict[str, Any] = {}
                for col in columns:
                    val = row.values[columns.index(col)]
                    record[col] = self._convert_value(val)
                rows.append(record)
            return rows

    @staticmethod
    def _convert_value(val) -> Any:
        """将 NebulaGraph ValueWrapper 转换为 Python 原生类型。"""
        vtype = val.getType()
        if vtype == 7:   # STRING
            return val.asString()
        if vtype == 1:   # INT
            return val.asInt()
        if vtype == 4:   # DOUBLE
            return val.asDouble()
        if vtype == 11:  # LIST
            return [NebulaStorage._convert_value(i) for i in val.asList()]
        # TODO: 按需扩展 DATE、TIME、MAP 等类型
        return str(val)

    def upsert_vertex(
        self, tag: str, vid: str, props: Dict[str, Any]
    ) -> bool:
        """
        插入或更新顶点（INSERT VERTEX IF NOT EXISTS）。
        """
        if not props:
            raise ValueError("props cannot be empty")

        # 构建属性赋值，字符串需加引号
        assignments = []
        for k, v in props.items():
            if isinstance(v, str):
                assignments.append(f'{k}="{v}"')
            else:
                assignments.append(f'{k}={v}')
        prop_str = ",".join(assignments)
        fields = ",".join(props.keys())

        query = (
            f'INSERT VERTEX IF NOT EXISTS {tag}({fields}) '
            f'VALUES "{vid}":({prop_str})'
        )
        self.execute(query)
        return True

    def upsert_edge(
        self,
        edge_type: str,
        src: str,
        dst: str,
        props: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        插入或更新边（INSERT EDGE IF NOT EXISTS）。
        """
        if props:
            assignments = []
            for k, v in props.items():
                if isinstance(v, str):
                    assignments.append(f'{k}="{v}"')
                else:
                    assignments.append(f'{k}={v}')
            prop_str = ",".join(assignments)
            fields = ",".join(props.keys())
            query = (
                f'INSERT EDGE IF NOT EXISTS {edge_type}({fields}) '
                f'VALUES "{src}"->"{dst}":({prop_str})'
            )
        else:
            query = (
                f'INSERT EDGE IF NOT EXISTS {edge_type}() '
                f'VALUES "{src}"->"{dst}":()'
            )
        self.execute(query)
        return True

    def close(self) -> None:
        """优雅关闭连接池。"""
        if self._pool:
            self._pool.close()
            logger.info("NebulaGraph connection pool closed")
