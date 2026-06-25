"""轻量级 CDP WebSocket 客户端"""
import asyncio
import json
import logging
import websockets

logger = logging.getLogger(__name__)  # 日志记录器


class EventRegistry:
    """事件注册表，处理 CDP 事件"""
    
    def handle_event(self, method: str, params: dict, session_id: str = None):
        """处理事件，默认空操作"""
        pass  # 可被外部替换


class CDPClient:
    """轻量级 CDP WebSocket 客户端"""
    
    def __init__(self, url: str):
        """初始化客户端
        
        Args:
            url: WebSocket 连接 URL
        """
        self.url = url
        self._ws = None  # WebSocket 连接对象
        self._pending = {}  # 等待响应的 Future 字典 {id: Future}
        self._next_id = 1  # 消息 ID 递增计数器
        self._event_registry = EventRegistry()  # 事件注册表
    
    async def start(self):
        """建立 WebSocket 连接并启动接收循环"""
        try:
            self._ws = await websockets.connect(self.url)  # 建立连接
            logger.info(f"已连接到 CDP: {self.url}")
            await self._receive_loop()  # 启动接收循环
        except Exception as e:
            logger.error(f"连接失败: {e}")
            raise
    
    async def send_raw(self, method: str, params: dict = None, session_id: str = None) -> dict:
        """发送 CDP 命令并等待响应
        
        Args:
            method: CDP 方法名
            params: 方法参数
            session_id: 会话 ID（可选）
            
        Returns:
            响应中的 result 字段
            
        Raises:
            Exception: 响应包含错误或超时
        """
        msg_id = self._next_id
        self._next_id += 1  # 递增 ID
        
        # 构建消息
        message = {"id": msg_id, "method": method}
        if params:
            message["params"] = params
        if session_id:
            message["sessionId"] = session_id
        
        # 创建 Future 等待响应
        future = asyncio.Future()
        self._pending[msg_id] = future
        
        try:
            # 发送消息
            await self._ws.send(json.dumps(message))
            
            # 等待响应，超时 30 秒
            response = await asyncio.wait_for(future, timeout=30.0)
            
            # 检查错误
            if "error" in response:
                raise Exception(f"CDP 错误: {response['error']}")
            
            return response.get("result", {})
            
        except asyncio.TimeoutError:
            raise Exception(f"命令超时: {method}")
        finally:
            # 清理 pending
            self._pending.pop(msg_id, None)
    
    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message in self._ws:
                data = json.loads(message)  # 解析 JSON
                
                if "id" in data:
                    # 响应消息，路由到对应的 Future
                    msg_id = data["id"]
                    if msg_id in self._pending:
                        self._pending[msg_id].set_result(data)
                else:
                    # 事件消息
                    method = data.get("method", "")
                    params = data.get("params", {})
                    session_id = data.get("sessionId")
                    self._event_registry.handle_event(method, params, session_id)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket 连接已关闭")
        except Exception as e:
            logger.error(f"接收消息错误: {e}")
        finally:
            # 取消所有 pending Future
            for future in self._pending.values():
                if not future.done():
                    future.cancel()
            self._pending.clear()
