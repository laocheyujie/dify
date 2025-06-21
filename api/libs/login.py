from functools import wraps
from typing import Any

from flask import current_app, g, has_request_context, request
from flask_login import user_logged_in  # type: ignore
from flask_login.config import EXEMPT_METHODS  # type: ignore
from werkzeug.exceptions import Unauthorized
from werkzeug.local import LocalProxy

from configs import dify_config
from extensions.ext_database import db
from models.account import Account, Tenant, TenantAccountJoin
from models.model import EndUser

#: A proxy for the current user. If no user is logged in, this will be an
#: anonymous user
current_user: Any = LocalProxy(lambda: _get_user())


def login_required(func):
    """
    NOTE: 在调用视图函数前确保用户已登录并认证，如果未认证，则调用 LoginManager.unauthorized 回调。
    在单元测试期间可以通过设置 LOGIN_DISABLED 为 True 来禁用认证检查，便于测试。
    指出根据 W3 的 CORS 指南，HTTP OPTIONS 请求不需要进行登录检查。
    
    If you decorate a view with this, it will ensure that the current user is
    logged in and authenticated before calling the actual view. (If they are
    not, it calls the :attr:`LoginManager.unauthorized` callback.) For
    example::

        @app.route('/post')
        @login_required
        def post():
            pass

    If there are only certain times you need to require that your user is
    logged in, you can do so with::

        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()

    ...which is essentially the code that this function adds to your views.

    It can be convenient to globally turn off authentication when unit testing.
    To enable this, if the application configuration variable `LOGIN_DISABLED`
    is set to `True`, this decorator will be ignored.

    .. Note ::

        Per `W3 guidelines for CORS preflight requests
        <http://www.w3.org/TR/cors/#cross-origin-request-with-preflight-0>`_,
        HTTP ``OPTIONS`` requests are exempt from login checks.

    :param func: The view function to decorate.
    :type func: function
    
    NOTE: 参数 func 是被装饰的视图函数
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if dify_config.ADMIN_API_KEY_ENABLE:
            if auth_header:
                if " " not in auth_header:
                    raise Unauthorized("Invalid Authorization header format. Expected 'Bearer <api-key>' format.")
                auth_scheme, auth_token = auth_header.split(None, 1)
                auth_scheme = auth_scheme.lower()
                if auth_scheme != "bearer":
                    raise Unauthorized("Invalid Authorization header format. Expected 'Bearer <api-key>' format.")

                # NOTE: 获取配置中的 ADMIN_API_KEY，并与从请求中提取的 auth_token 进行比较
                admin_api_key = dify_config.ADMIN_API_KEY
                if admin_api_key:
                    if admin_api_key == auth_token:
                        # NOTE: 从请求头中获取工作区 ID（X-WORKSPACE-ID）
                        workspace_id = request.headers.get("X-WORKSPACE-ID")
                        if workspace_id:
                            # NOTE: 查询数据库，检查该工作区 ID 是否存在，并验证当前用户是否为该租户的所有者
                            tenant_account_join = (
                                db.session.query(Tenant, TenantAccountJoin)
                                .filter(Tenant.id == workspace_id)
                                .filter(TenantAccountJoin.tenant_id == Tenant.id)
                                .filter(TenantAccountJoin.role == "owner")
                                .one_or_none()
                            )
                            if tenant_account_join:
                                # NOTE: 如果找到了租户账户关系，获取账户信息并更新请求上下文，以登录该用户，并发送用户登录的信号
                                tenant, ta = tenant_account_join
                                account = db.session.query(Account).filter_by(id=ta.account_id).first()
                                # Login admin
                                if account:
                                    account.current_tenant = tenant
                                    current_app.login_manager._update_request_context_with_user(account)  # type: ignore
                                    user_logged_in.send(current_app._get_current_object(), user=_get_user())  # type: ignore
        if request.method in EXEMPT_METHODS or dify_config.LOGIN_DISABLED:
            # NOTE: 检查请求方法是否在被豁免的方法列表中，或是否禁用登录。如果是，则跳过认证检查
            pass
        elif not current_user.is_authenticated:
            # NOTE: 如果用户未认证，则返回未授权响应
            return current_app.login_manager.unauthorized()  # type: ignore

        # flask 1.x compatibility
        # current_app.ensure_sync is only available in Flask >= 2.0
        if callable(getattr(current_app, "ensure_sync", None)):
            # NOTE: 检查 Flask 版本是否支持 ensure_sync，如果支持，则异步调用装饰的视图函数
            return current_app.ensure_sync(func)(*args, **kwargs)
        return func(*args, **kwargs)
    
    # NOTE: 如果用户已认证，直接调用并返回原始的视图函数
    return decorated_view


def _get_user() -> EndUser | Account | None:
    if has_request_context():
        if "_login_user" not in g:
            current_app.login_manager._load_user()  # type: ignore

        return g._login_user  # type: ignore

    return None
