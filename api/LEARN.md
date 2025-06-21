# API-Key 与 Bearer Token 鉴权方式

## API-Key 与 Bearer Token 鉴权的区别

| 特性       | API-Key                                  | Bearer Token                                       |
|------------|-------------------------------------------|----------------------------------------------------|
| 定义       | 一种用于识别调用者身份的密钥              | 一种令牌，表示用户已经通过认证                    |
| 格式       | 通常为简单的字符串                        | 通常为 `"Bearer <token>"` 格式                     |
| 存储位置   | 可以在请求头、URL 查询参数或请求体中      | 通常存储在请求头中                                |
| 认证过程   | 直接使用 API-Key                          | 需要通过认证流程获取令牌                          |
| 有效期     | 通常没有有效期或长期有效                  | 通常有有效期（如几分钟到几小时）                  |
| 安全性     | 相对较低，容易被截获                      | 更高，通过过期和刷新机制提高安全性                |
| 使用场景   | 简单的 API 访问                           | 用户身份验证和授权                                |
| 撤销机制   | 需要手动更换或删除 API-Key               | 可以通过令牌失效或刷新实现                        |
| 适用性     | 适用于无状态 API 调用                    | 适用于需要用户会话的应用                          |


## DIFY 中的鉴权方式

- `console`（URL 前缀`/console/api`）: `Bearer Token`, 通过 `login_required` 装饰器实现
- `web`（URL 前缀`/api`）: `Bearer Token`, 通过继承 `WebApiResource`，即 `validate_jwt_token` 装饰器实现
- `service_api`（URL 前缀`/v1`）: `API-Key`, 通过 `validate_app_token` 装饰器实现


## console (`Bearer Token`)

### LoginApi

位于：`dify/api/controllers/console/auth/login.py`

`post`返回结果示例：
```json
{
    "result": "success",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZWJiZjI1YmUtZWM4NS00ZDY4LTlkZDItNWJjMmVlMjg1NWU0IiwiZXhwIjoxNzMwNjg5Mjk4LCJpc3MiOiJTRUxGX0hPU1RFRCIsInN1YiI6IkNvbnNvbGUgQVBJIFBhc3Nwb3J0In0.EPfEaeoDY8NVeS7TDC95-B0rvFYjH9BVqiFY9IwYcVQ",
        "refresh_token": "32a914bb7d7dac9b1b7b5ba98d6584007acbcba4638374d8e0171877f5c9eee34eae400917aadc433d7801181367579dd72894ae8f512aaba00929ab98bf509f"
    }
}
```

### AccountService

位于：`dify/api/services/account_service.py`

#### AccountService.authenticate()

`account = AccountService.authenticate(args["email"], args["password"])`该方法实现了基于邮箱和密码的账户认证流程，包括账户查询、状态检查、密码哈希、首次登录处理和状态更新。如果所有条件都满足，最后将返回一个有效的 `Account` 对象


#### AccountService.login()

`token_pair = AccountService.login(account=account, ip_address=extract_remote_ip(request))`

#### AccountService.get_account_jwt_token()

`AccountService.get_account_jwt_token(account=account)`

该方法主要是生成 jwt token


#### _generate_refresh_token()

该方法主要是生成 refresh token

#### AccountService._store_refresh_token()

`AccountService._store_refresh_token(refresh_token, account.id)`

该方法的作用是将刷新令牌和账户 ID 以键值对的形式存储到 Redis 中，并设置过期时间，以便后续的身份验证和管理。当用户登录或需要刷新令牌时，可以快速查找这些信息

#### AccountService.reset_login_error_rate_limit()

`AccountService.reset_login_error_rate_limit(args["email"])`

该方法用于重置指定邮箱的登录错误次数限制，通过删除与该邮箱相关的 Redis 键实现

#### AccountService.logout()

`AccountService.logout(account=account)`

该方法用于用户登出操作，首先尝试从 Redis 中获取用户的刷新令牌，如果存在，则删除该令牌，以实现用户登出的效果



## web (`Bearer Token`)

位于：`dify/api/controllers/web/wraps.py`

### validate_jwt_token

用于在调用视图函数之前验证 JWT。它会解码 JWT，提取出相关的用户信息，并将其传递给视图函数，这里面的类基本都继承自 `WebApiResource` 类

### WebApiResource



## service_api (`API-Key`)

位于：`dify/api/controllers/service_api/wraps.py`，只有这一个地方的 API 使用的是 `API-Key` 鉴权方式，其它地方均使用 `Bearer Token` 鉴权方式。

### validate_app_token
`validate_app_token` 用于验证应用程序的 API 令牌，检查相关的应用和租户状态，并根据需要提取用户信息，为后续的视图函数提供必要的上下文