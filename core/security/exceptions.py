"""
安全相关异常类
"""


class PermissionDeniedError(Exception):
    """操作因安全审核被拒绝时抛出"""
    pass


class SecurityViolationError(Exception):
    """检测到安全违规时抛出"""
    pass
