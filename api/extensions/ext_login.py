import json

import flask_login  # type: ignore
from flask import Response, request
from flask_login import user_loaded_from_request, user_logged_in
from werkzeug.exceptions import Unauthorized

import contexts
from dify_app import DifyApp
from libs.passport import PassportService
from services.account_service import AccountService

login_manager = flask_login.LoginManager()


# Flask-Login configuration
@login_manager.request_loader
def load_user_from_request(request_from_flask_login):
    """Load user based on the request."""
    # NOTE: 只处理 "console" 和 "inner_api" 这两个蓝图下的请求
    if request.blueprint not in {"console", "inner_api"}:
        return None
    # Check if the user_id contains a dot, indicating the old format
    # NOTE: 支持两种认证方式：
    # 1. 从 HTTP 请求头中获取 Authorization 字段
    # 2. 从 URL 请求参数中获取 _token 字段
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        auth_token = request.args.get("_token")
        if not auth_token:
            raise Unauthorized("Invalid Authorization token.")
    else:
        if " " not in auth_header:
            raise Unauthorized("Invalid Authorization header format. Expected 'Bearer <api-key>' format.")
        auth_scheme, auth_token = auth_header.split(None, 1)
        auth_scheme = auth_scheme.lower()
        if auth_scheme != "bearer":
            raise Unauthorized("Invalid Authorization header format. Expected 'Bearer <api-key>' format.")

    # NOTE: 使用 PassportService 验证 token
    decoded = PassportService().verify(auth_token)
    user_id = decoded.get("user_id")

    # NOTE: 使用 AccountService 加载用户账户信息
    logged_in_account = AccountService.load_logged_in_account(account_id=user_id)
    return logged_in_account


# NOTE: 用户登录事件处理
# @user_logged_in.connect 和 @user_loaded_from_request.connect 是 Flask-Login 提供的事件监听器，用于在特定事件发生时触发回调函数
# @user_logged_in.connect 当用户通过正常的登录流程（如登录表单）成功登录时触发，通常用于处理用户主动登录的情况
# @user_loaded_from_request.connect 当用户通过请求加载器（如 API 令牌）被加载时触发，通常用于 API 认证等场景，用户通过令牌而不是登录表单进行认证
@user_logged_in.connect
@user_loaded_from_request.connect
def on_user_logged_in(_sender, user):
    """Called when a user logged in."""
    if user:
        # NOTE: 当用户成功登录时：
        # 设置当前租户 ID 到上下文中
        # 这确保了在后续请求中可以访问到正确的租户信息
        # NOTE: contexts 是一个上下文管理工具，在这个代码中主要用于管理请求级别的上下文数据
        # 这行代码的作用是：
        # - 将当前用户的租户 ID 存储在请求上下文中
        # - 这个上下文数据在整个请求生命周期内都是可用的
        # - 其他代码可以通过 contexts.tenant_id.get() 来获取当前租户 ID
        
        # 使用 contexts 的好处是：
        # - 实现了请求级别的数据隔离
        # - 不需要在每个函数中传递租户 ID 参数
        # - 支持多租户系统，确保不同租户的数据互不干扰
        # - 线程安全，每个请求都有自己独立的上下文
        
        # 这种设计模式在微服务架构中特别有用，因为它：
        # - 简化了代码，避免了参数传递的复杂性
        # - 提供了清晰的数据访问边界
        # - 支持多租户系统的数据隔离
        # 便于实现请求级别的中间件和拦截器
        contexts.tenant_id.set(user.current_tenant_id)


# NOTE: 未授权处理
# 未授权的判断逻辑：当 load_user_from_request 函数返回 None 或抛出异常时
@login_manager.unauthorized_handler
def unauthorized_handler():
    """Handle unauthorized requests."""
    return Response(
        json.dumps({"code": "unauthorized", "message": "Unauthorized."}),
        status=401,
        content_type="application/json",
    )


def init_app(app: DifyApp):
    login_manager.init_app(app)
