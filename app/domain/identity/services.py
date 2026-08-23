"""身份域服务 — 密码策略与密码哈希（纯函数，零框架依赖）

由原 app/utils/password.py 并入 domain/identity，
按 DDD 分层作为身份域的核心领域服务。
"""

import re

import bcrypt

_UPPER_RE = re.compile(r"[A-Z]")
_LOWER_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def hash_password(password: str) -> str:
    """bcrypt 哈希密码"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


class PasswordPolicy:
    """密码强度策略 — 纯函数校验"""

    MIN_LENGTH = 8
    MAX_LENGTH = 64

    @classmethod
    def validate(cls, password: str) -> None:
        """校验密码强度，不满足时抛出 ValueError

        要求：8-64 位，同时包含大写字母、小写字母、数字、特殊字符。
        """
        if not password or len(password) < cls.MIN_LENGTH:
            raise ValueError(f"Password must be at least {cls.MIN_LENGTH} characters")
        if len(password) > cls.MAX_LENGTH:
            raise ValueError(f"Password must be at most {cls.MAX_LENGTH} characters")

        missing = []
        if not _UPPER_RE.search(password):
            missing.append("uppercase letter")
        if not _LOWER_RE.search(password):
            missing.append("lowercase letter")
        if not _DIGIT_RE.search(password):
            missing.append("digit")
        if not _SPECIAL_RE.search(password):
            missing.append("special character")
        if missing:
            raise ValueError("Password must contain " + ", ".join(missing))

    @classmethod
    def strength_score(cls, password: str) -> int:
        """返回密码强度评分 0-100（用于注册页实时提示）"""
        if not password:
            return 0
        score = 0
        length = len(password)
        if length >= cls.MIN_LENGTH:
            score += 20
        if length >= 12:
            score += 10
        if length >= 16:
            score += 10
        if _UPPER_RE.search(password) and _LOWER_RE.search(password):
            score += 20
        if _DIGIT_RE.search(password):
            score += 20
        if _SPECIAL_RE.search(password):
            score += 20
        return min(score, 100)
