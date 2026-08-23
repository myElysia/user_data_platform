"""安全域服务 — TotpService/RiskAssessmentService/FingerprintService（纯逻辑，零框架依赖）

由原 app/core/security.py（engine.py）重组：
- 设备指纹生成与信任衰减 → FingerprintService
- 风险评分 → RiskAssessmentService（0-100 规则引擎）
- Token 会话绑定 → SessionBinding
- TOTP → TotpService（pyotp）
DB 交互部分（设备评估/MFA 校验）迁至基础设施仓储（SqlDeviceRepository 等）。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, List, Optional

import pyotp

from app.domain.security.value_objects import RiskScore

# ---------------------------------------------------------------------------
# 设备指纹服务
# ---------------------------------------------------------------------------


class FingerprintService:
    """设备指纹生成（增强版：ip + ua + accept-language + 额外头）"""

    @staticmethod
    def generate_fingerprint(
        ip_address: str,
        user_agent: str,
        accept_language: str = "",
        extra_headers: Optional[dict[str, str]] = None,
    ) -> str:
        """生成设备指纹哈希（SHA256）"""
        components = [ip_address, user_agent, accept_language]
        if extra_headers:
            components.extend(sorted(extra_headers.values()))
        concatenated = "|".join(components)
        return sha256(concatenated.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 风险评估引擎（0-100 规则引擎）
# ---------------------------------------------------------------------------


@dataclass
class RiskContext:
    """风险评估输入上下文"""

    ip: str
    is_new_device: bool = False
    is_new_ip: bool = False
    failed_attempts: int = 0
    recent_ip_count: int = 1  # 短时间窗口内出现过的 IP 数量
    current_hour: Optional[int] = None  # None = 取当前时间
    is_blacklisted_ip: bool = False


@dataclass
class RiskAssessment:
    """风险评估结果"""

    score: int
    triggered_rules: List[str] = field(default_factory=list)
    action: str = "ALLOW"


class RiskAssessmentService:
    """风险评估规则引擎 — 纯函数，输入上下文输出评分与动作

    规则（可命中多条，分数累加，上限 100）：
    - new_device: 首次出现的新设备 +30
    - new_ip: 新 IP +20
    - failed_attempts: 登录失败次数 >= 3 +30
    - rapid_ip_switch: 短时间多 IP 切换（>= 3 个）+25
    - unusual_hour: 异常时段 0-5 点 +15
    - blacklisted_ip: 高风险 IP 黑名单 +50

    判定：score < 40 → ALLOW；40-70 → CHALLENGE_2FA；> 70 → BLOCK
    """

    RULE_NEW_DEVICE = ("new_device", 30)
    RULE_NEW_IP = ("new_ip", 20)
    RULE_FAILED_ATTEMPTS = ("failed_attempts", 30)
    RULE_RAPID_IP_SWITCH = ("rapid_ip_switch", 25)
    RULE_UNUSUAL_HOUR = ("unusual_hour", 15)
    RULE_BLACKLISTED_IP = ("blacklisted_ip", 50)

    FAILED_ATTEMPTS_THRESHOLD = 3
    IP_SWITCH_THRESHOLD = 3
    UNUSUAL_HOURS = range(0, 6)  # 0-5 点

    @classmethod
    def assess(cls, context: RiskContext) -> RiskAssessment:
        """执行风险评估，返回评分与判定动作"""
        score = 0
        triggered: List[str] = []

        def _apply(rule: tuple[str, int], condition: bool) -> None:
            nonlocal score
            if condition:
                score += rule[1]
                triggered.append(rule[0])

        _apply(cls.RULE_NEW_DEVICE, context.is_new_device)
        _apply(cls.RULE_NEW_IP, context.is_new_ip)
        _apply(
            cls.RULE_FAILED_ATTEMPTS,
            context.failed_attempts >= cls.FAILED_ATTEMPTS_THRESHOLD,
        )
        _apply(
            cls.RULE_RAPID_IP_SWITCH,
            context.recent_ip_count >= cls.IP_SWITCH_THRESHOLD,
        )
        hour = (
            context.current_hour
            if context.current_hour is not None
            else datetime.now(timezone.utc).hour
        )
        _apply(cls.RULE_UNUSUAL_HOUR, hour in cls.UNUSUAL_HOURS)
        _apply(cls.RULE_BLACKLISTED_IP, context.is_blacklisted_ip)

        score = min(score, 100)
        return RiskAssessment(
            score=score,
            triggered_rules=triggered,
            action=RiskScore(score).action.value,
        )


# ---------------------------------------------------------------------------
# Token 会话绑定
# ---------------------------------------------------------------------------


class SessionBinding:
    """Token 与设备/会话绑定验证（纯逻辑）"""

    @staticmethod
    def create_session_context(
        fingerprint_hash: str,
        session_id: str,
        ip_address: str,
    ) -> dict[str, str]:
        return {
            "fp_hash": fingerprint_hash,
            "sid": session_id,
            "ip": ip_address,
        }

    @classmethod
    def verify_binding(
        cls,
        token_claims: dict[str, Any],
        current_fingerprint: str,
        current_ip: str,
    ) -> bool:
        """校验 token 绑定的设备指纹/IP 与当前请求是否一致"""
        bound_fp = token_claims.get("fp_hash")
        bound_ip = token_claims.get("ip")

        if bound_fp and bound_fp != current_fingerprint:
            return False
        if bound_ip and bound_ip != current_ip:
            return False
        return True


# ---------------------------------------------------------------------------
# TOTP 双因素认证服务
# ---------------------------------------------------------------------------


class TotpService:
    """TOTP 双因素认证服务（pyotp 封装）"""

    def __init__(
        self,
        issuer: str = "user_platform",
        digits: int = 6,
        interval: int = 30,
    ):
        self._issuer = issuer
        self._digits = digits
        self._interval = interval

    def generate_secret(self) -> str:
        """生成随机 TOTP 密钥（base32）"""
        return pyotp.random_base32()

    def build_uri(self, secret: str, account_name: str) -> str:
        """生成 otpauth:// URI（供二维码扫码绑定）"""
        totp = pyotp.TOTP(secret, digits=self._digits, interval=self._interval)
        return totp.provisioning_uri(name=account_name, issuer_name=self._issuer)

    def verify(self, secret: str, code: str, valid_window: int = 1) -> bool:
        """校验 TOTP 动态码（默认允许 ±1 个时间窗口漂移）"""
        try:
            totp = pyotp.TOTP(secret, digits=self._digits, interval=self._interval)
            return totp.verify(code, valid_window=valid_window)
        except Exception:
            return False

    def current_code(self, secret: str) -> str:
        """生成当前时间窗的动态码（调试用）"""
        return pyotp.TOTP(secret, digits=self._digits, interval=self._interval).now()
