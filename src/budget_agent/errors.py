"""可展示的稳定错误，不把服务响应正文或密钥写入记录。"""


class AgentError(Exception):
    """已知的可恢复运行错误。"""


class ModuleNotReady(AgentError):
    """正式业务尚未实现；严禁用空结果冒充成功。"""


class ToolLimitReached(AgentError):
    """调用预算或运行时间已耗尽。"""


class ModelError(AgentError):
    """模型连接或结构化输出失败。"""
