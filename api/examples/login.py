import re
import base64
import secrets
from datetime import datetime, timedelta, UTC
from examples.passport import PassportService
from examples.password import valid_password, hash_password, compare_password


def valid_email(email):
    # Define a regex pattern for email addresses
    pattern = r"^[\w\.!#$%&'*+\-/=?^_`{|}~]+@([\w-]+\.)+[\w-]{2,}$"
    # Check if the email matches the pattern
    if re.match(pattern, email) is not None:
        return email

    error = "{email} is not a valid email.".format(email=email)
    raise ValueError(error)


def generate_refresh_token(length: int = 64):
    """ 生成刷新令牌 """
    token = secrets.token_hex(length)
    return token
    

class SimpleAuthService:
    def __init__(self):
        # 模拟数据库
        self.db = {}
        # 模拟 Redis
        self.redis = {}
        
    def _generate_jwt_access_token(self, email: str) -> str:
        """生成访问令牌"""
        payload = {
            "email": email,
            "exp": int((datetime.now(UTC) + timedelta(minutes=15)).timestamp())  # 15分钟过期
        }
        token = PassportService().issue(payload)
        return token
    
    def _generate_refresh_token(self, email: str) -> str:
        """生成刷新令牌"""
        refresh_token = generate_refresh_token()  # 生成随机令牌
        return refresh_token
    
    def _store_refresh_token(self, refresh_token: str, email: str) -> None:
        """存储刷新令牌"""
        self.redis[refresh_token] = {
            "email": email,
            "expires_at": datetime.now(UTC) + timedelta(days=7)  # 7天过期
        }
    
    def _delete_refresh_token(self, refresh_token: str) -> None:
        """删除刷新令牌"""
        del self.redis[refresh_token]

    def register(self, email: str, password: str) -> dict:
        """注册新用户"""
        # 验证邮箱和密码
        email = valid_email(email)
        password = valid_password(password)
        
        # 生成随机盐值，用于加解密
        salt = secrets.token_bytes(16)
        # 将盐值转换为 base64 字符串，用于存储
        salt_base64 = base64.b64encode(salt).decode()
        
        # 密码加盐哈希
        password_hashed = hash_password(password, salt)
        # 将密码哈希转换为 base64 字符串，用于存储
        password_hashed_base64 = base64.b64encode(password_hashed).decode()
        
        # 数据库存储用户信息
        user = {
            "email": email,
            "password": password_hashed_base64,
            "salt": salt_base64
        }
        self.db[email] = user
        return user
    
    def authenticate(self, email: str, password: str) -> bool:
        """验证用户密码"""
        # 获取用户信息
        user = self.db.get(email)
        if not user:
            raise ValueError("用户不存在")
            
        if password and user["password"] is None:
            salt = base64.b64decode(user["salt"])
            salt_base64 = base64.b64encode(salt).decode()
            password_hashed = hash_password(password, salt)
            password_hashed_base64 = base64.b64encode(password_hashed).decode()
            user["password"] = password_hashed_base64
            user["salt"] = salt_base64
            self.db[email] = user
        
        if user["password"] is None or not compare_password(password, user["password"], user["salt"]):
            raise ValueError("密码错误")
        
        return True

    def login(self, email: str) -> dict:
        """用户登录"""
        # 生成 access token
        access_token = self._generate_jwt_access_token(email)
        # 生成 refresh token
        refresh_token = self._generate_refresh_token(email)
        # 存储刷新令牌
        self._store_refresh_token(refresh_token, email)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    def logout(self, email: str) -> None:
        """用户退出"""
        # 删除刷新令牌
        refresh_token = self.redis.get(email)
        if refresh_token:
            del self.redis[refresh_token]
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        """使用刷新令牌获取新的访问令牌"""
        # 验证刷新令牌
        token_data = self.redis.get(refresh_token)
        if not token_data or token_data["expires_at"] < datetime.now(UTC):
            raise ValueError("刷新令牌无效或已过期")
            
        # 生成新的访问令牌
        new_access_token = self._generate_jwt_access_token(token_data["email"])
        # 生成新的刷新令牌
        new_refresh_token = self._generate_refresh_token(token_data["email"])
        # 存储新的刷新令牌
        self._store_refresh_token(new_refresh_token, token_data["email"])
        
        # 删除旧的刷新令牌
        self._delete_refresh_token(refresh_token)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }

# 使用示例
def main():
    auth_service = SimpleAuthService()
    
    # 注册用户
    user = auth_service.register("test@example.com", "password123")
    print("注册成功！")
    print("用户信息:", user)
    
    try:
        # 登录
        if not auth_service.authenticate("test@example.com", "password123"):
            raise ValueError("密码错误")
        tokens = auth_service.login("test@example.com")
        print("登录成功！")
        print("Access Token:", tokens["access_token"])
        print("Refresh Token:", tokens["refresh_token"])
        
        # 使用刷新令牌获取新的令牌
        new_tokens = auth_service.refresh_access_token(tokens["refresh_token"])
        print("\n刷新令牌成功！")
        print("New Access Token:", new_tokens["access_token"])
        print("New Refresh Token:", new_tokens["refresh_token"])
        
    except ValueError as e:
        print("错误:", str(e))


if __name__ == "__main__":
    main()