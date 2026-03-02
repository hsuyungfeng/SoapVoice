"""
安全認證模組

提供 API Key 驗證與 JWT Token 認證功能
"""

import os
import time
import logging
import secrets
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    """API Key 資料結構"""
    key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    rate_limit: int = 1000  # 每小時請求數


@dataclass
class TokenPayload:
    """JWT Token 負載"""
    sub: str  # 使用者 ID
    exp: datetime  # 過期時間
    iat: datetime  # 發行時間
    role: str = "user"  # 角色


class SecurityManager:
    """安全管理器"""

    def __init__(self, secret_key: Optional[str] = None):
        """
        初始化安全管理器

        Args:
            secret_key: JWT 簽密鑰，預設從環境變數讀取
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "dev-secret-key")
        self._api_keys: Dict[str, APIKey] = {}
        self._token_blacklist: set = set()
        
        # 初始化預設 API Key
        self._init_default_api_key()

    def _init_default_api_key(self) -> None:
        """初始化預設 API Key"""
        default_key = os.getenv("DEFAULT_API_KEY", "soapvoice-dev-key")
        self.create_api_key(
            name="Default Development Key",
            key=default_key,
            rate_limit=10000,
        )

    def create_api_key(
        self,
        name: str,
        key: Optional[str] = None,
        expires_in_hours: Optional[int] = None,
        rate_limit: int = 1000,
    ) -> APIKey:
        """
        建立 API Key

        Args:
            name: API Key 名稱
            key: 自定義 Key，預設自動生成
            expires_in_hours: 過期時間 (小時)
            rate_limit: 每小時請求數限制

        Returns:
            APIKey 實例
        """
        api_key = key or secrets.token_urlsafe(32)
        
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now() + timedelta(hours=expires_in_hours)

        api_key_obj = APIKey(
            key=api_key,
            name=name,
            created_at=datetime.now(),
            expires_at=expires_at,
            is_active=True,
            rate_limit=rate_limit,
        )
        
        self._api_keys[api_key] = api_key_obj
        logger.info(f"Created API key: {name}")
        
        return api_key_obj

    def validate_api_key(self, api_key: str) -> bool:
        """
        驗證 API Key

        Args:
            api_key: API Key

        Returns:
            是否有效
        """
        if api_key not in self._api_keys:
            return False

        key_obj = self._api_keys[api_key]
        
        if not key_obj.is_active:
            return False
        
        if key_obj.expires_at and datetime.now() > key_obj.expires_at:
            key_obj.is_active = False
            return False
        
        return True

    def create_token(
        self,
        user_id: str,
        role: str = "user",
        expires_in_hours: int = 24,
    ) -> str:
        """
        建立 JWT Token

        Args:
            user_id: 使用者 ID
            role: 使用者角色
            expires_in_hours: 過期時間 (小時)

        Returns:
            JWT Token
        """
        now = datetime.now()
        payload = TokenPayload(
            sub=user_id,
            exp=now + timedelta(hours=expires_in_hours),
            iat=now,
            role=role,
        )
        
        token = jwt.encode(
            payload.__dict__,
            self.secret_key,
            algorithm="HS256",
        )
        
        logger.info(f"Created token for user: {user_id}")
        return token

    def validate_token(self, token: str) -> TokenPayload:
        """
        驗證 JWT Token

        Args:
            token: JWT Token

        Returns:
            TokenPayload 實例

        Raises:
            HTTPException: Token 無效或過期
        """
        if token in self._token_blacklist:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )

        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
            )
            
            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"]),
                role=payload.get("role", "user"),
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    def revoke_token(self, token: str) -> None:
        """
        撤銷 Token

        Args:
            token: JWT Token
        """
        self._token_blacklist.add(token)
        logger.info("Token revoked")

    def delete_api_key(self, api_key: str) -> bool:
        """
        刪除 API Key

        Args:
            api_key: API Key

        Returns:
            是否成功刪除
        """
        if api_key in self._api_keys:
            del self._api_keys[api_key]
            logger.info(f"Deleted API key: {api_key}")
            return True
        return False

    def list_api_keys(self) -> list:
        """
        列出所有 API Key (不包含敏感資訊)

        Returns:
            API Key 資訊列表
        """
        return [
            {
                "name": key.name,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "is_active": key.is_active,
                "rate_limit": key.rate_limit,
            }
            for key in self._api_keys.values()
        ]


# 全域安全管理器實例
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """獲取全域安全管理器實例"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# FastAPI Security Schemes
http_bearer = HTTPBearer(auto_error=False)
http_api_key = HTTPBearer(auto_error=False, scheme_name="API-Key")


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_api_key),
) -> str:
    """
    驗證 API Key

    Args:
        credentials: HTTP Authorization 憑證

    Returns:
        API Key

    Raises:
        HTTPException: 認證失敗
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )
    
    api_key = credentials.credentials
    security_manager = get_security_manager()
    
    if not security_manager.validate_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    
    return api_key


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> TokenPayload:
    """
    驗證 JWT Token

    Args:
        credentials: HTTP Authorization 憑證

    Returns:
        TokenPayload 實例

    Raises:
        HTTPException: 認證失敗
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
    
    token = credentials.credentials
    security_manager = get_security_manager()
    
    return security_manager.validate_token(token)
