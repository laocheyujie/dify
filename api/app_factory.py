import logging
import time

from configs import dify_config
from contexts.wrapper import RecyclableContextVar
from dify_app import DifyApp


# ----------------------------
# Application Factory Function
# ----------------------------
def create_flask_app_with_configs() -> DifyApp:
    """
    create a raw flask app
    with configs loaded from .env file
    """
    dify_app = DifyApp(__name__)
    dify_app.config.from_mapping(dify_config.model_dump())

    # add before request hook
    @dify_app.before_request
    def before_request():
        # add an unique identifier to each request
        # NOTE: 为了解决在 Gunicorn（一个 Python WSGI HTTP 服务器）中使用线程回收（thread recycling）时的上下文变量问题
        RecyclableContextVar.increment_thread_recycles()

    return dify_app


def create_app() -> DifyApp:
    start_time = time.perf_counter()
    app = create_flask_app_with_configs()
    initialize_extensions(app)
    end_time = time.perf_counter()
    if dify_config.DEBUG:
        logging.info(f"Finished create_app ({round((end_time - start_time) * 1000, 2)} ms)")
    return app


def initialize_extensions(app: DifyApp):
    from extensions import (
        ext_app_metrics,
        ext_blueprints,
        ext_celery,
        ext_code_based_extension,
        ext_commands,
        ext_compress,
        ext_database,
        ext_hosting_provider,
        ext_import_modules,
        ext_logging,
        ext_login,
        ext_mail,
        ext_migrate,
        ext_otel,
        ext_otel_patch,
        ext_proxy_fix,
        ext_redis,
        ext_repositories,
        ext_sentry,
        ext_set_secretkey,
        ext_storage,
        ext_timezone,
        ext_warnings,
    )
    # NOTE:从extensions模块中导入各子模块配置，各子模块的内容及其组织方式都非常值得关注。
    # 将这些功能模块单独组织，然后在Flask应用程序中使用这些功能，增强应用的能力和灵活性。
    # 各模块的大概功能如下：
    # ext_blueprints：用于组织Flask应用的蓝图。

    extensions = [
        ext_timezone,                  # 用于处理时区
        ext_logging,                   # 用于日志记录
        ext_warnings,                  # 可能用于处理警告信息
        ext_import_modules,            # 用于动态导入模块
        ext_set_secretkey,             # 用于设置应用的密钥
        ext_compress,                  # 用于压缩响应数据
        ext_code_based_extension,      # 基于代码的扩展
        ext_database,                  # 用于数据库操作
        ext_app_metrics,               # 用于应用程序性能监控
        ext_migrate,                   # 用于数据库迁移
        ext_redis,                     # 用于与 Redis 数据库交互
        ext_storage,                   # 用于文件存储
        ext_repositories,              # 用于注册存储库操作
        ext_celery,                    # 用于集成Celery进行异步任务处理
        ext_login,                     # 用于用户登录管理
        ext_mail,                      # 用于发送邮件
        ext_hosting_provider,          # 与远程托管服务相关的扩展
        ext_sentry,                    # 用于错误监控和报告
        ext_proxy_fix,                 # 用于处理代理请求
        ext_blueprints,                # 用于组织Flask应用的蓝图
        ext_commands,                  # 用于定义自定义命令
        ext_otel_patch,
        ext_otel,                      
    ]
    for ext in extensions:
        short_name = ext.__name__.split(".")[-1]
        is_enabled = ext.is_enabled() if hasattr(ext, "is_enabled") else True
        # NOTE:如果模块未启用，而且在debug模式下，忽略该模块，不初始化到Flask应用程序中
        if not is_enabled:
            if dify_config.DEBUG:
                logging.info(f"Skipped {short_name}")
            continue

        start_time = time.perf_counter()
        ext.init_app(app)
        end_time = time.perf_counter()
        if dify_config.DEBUG:
            logging.info(f"Loaded {short_name} ({round((end_time - start_time) * 1000, 2)} ms)")


def create_migrations_app():
    # NOTE:定义一个名为create_migrations_app的函数，目的是创建并返回一个配置好的Flask应用实例，专门用于数据库迁移
    app = create_flask_app_with_configs()
    from extensions import ext_database, ext_migrate

    # Initialize only required extensions
    ext_database.init_app(app)
    ext_migrate.init_app(app)

    return app
