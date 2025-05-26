from datetime import timedelta

import pytz
from celery import Celery, Task  # type: ignore
from celery.schedules import crontab  # type: ignore

from configs import dify_config
from dify_app import DifyApp


def init_app(app: DifyApp) -> Celery:
    class FlaskTask(Task):
        # NOTE: 自定义的 Task 类，它确保每个 Celery 任务都在 Flask 应用上下文中运行
        # 这对于访问 Flask 的配置和功能很重要，因为任务可能需要访问 Flask 的配置、数据库连接等资源
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    broker_transport_options = {}

    if dify_config.CELERY_USE_SENTINEL:
        # NOTE: 配置了 Redis Sentinel 高可用方案，用于确保 Redis 服务的可靠性
        # Sentinel 是 Redis 的高可用性解决方案，能够监控 Redis 主从实例，在主实例故障时自动进行故障转移
        # 它是一个独立的进程，专门用来监控和管理 Redis 主从复制集群
        # 持续监控主从节点的健康状态
        # 当实例出现问题时发送警报
        # 主节点故障时自动选举新的主节点
        # 为客户端提供当前主节点的地址
        # Celery Worker → Sentinel → 主节点 Redis
        #                    ↓
        #   返回主节点地址: 192.168.1.100:6379
        broker_transport_options = {
            "master_name": dify_config.CELERY_SENTINEL_MASTER_NAME,               # Sentinel 配置中定义的主节点名称，Sentinel 通过这个名称来识别要监控的主从集群
            "sentinel_kwargs": {
                "socket_timeout": dify_config.CELERY_SENTINEL_SOCKET_TIMEOUT,     # 与 Sentinel 节点通信的超时时间，防止网络问题导致的长时间等待
            },
        }

    celery_app = Celery(
        app.name,
        task_cls=FlaskTask,
        broker=dify_config.CELERY_BROKER_URL,  # 任务代理（broker）URL，负责接收、存储和路由消息
        backend=dify_config.CELERY_BACKEND,    # 任务结果后端（backend）URL，负责存储任务执行结果
        task_ignore_result=True,               # 默认忽略任务结果（提高性能）
    )

    # Add SSL options to the Celery configuration
    ssl_options = {
        "ssl_cert_reqs": None,
        "ssl_ca_certs": None,
        "ssl_certfile": None,
        "ssl_keyfile": None,
    }

    celery_app.conf.update(
        result_backend=dify_config.CELERY_RESULT_BACKEND,   # 如果CELERY_BACKEND == "database"，则使用SQLAlchemy连接池，否则使用broker_url
        broker_transport_options=broker_transport_options,
        broker_connection_retry_on_startup=True,            # 启动时重试连接代理
        worker_log_format=dify_config.LOG_FORMAT,
        worker_task_log_format=dify_config.LOG_FORMAT,
        worker_hijack_root_logger=False,                    # 不劫持根日志记录器
        timezone=pytz.timezone(dify_config.LOG_TZ or "UTC"), # 设置时区
    )

    if dify_config.BROKER_USE_SSL:
        celery_app.conf.update(
            broker_use_ssl=ssl_options,  # Add the SSL options to the broker configuration
        )

    if dify_config.LOG_FILE:
        celery_app.conf.update(
            worker_logfile=dify_config.LOG_FILE,
        )

    # NOTE: 将当前的 Celery 应用实例设置为默认的全局 Celery 应用
    # 在配置完成后调用：确保所有配置（SSL、日志、调度等）都已经设置完毕
    # 在注册到 Flask 扩展前调用：使得 Flask 应用可以正确识别和使用这个默认的 Celery 实例
    # 为后续的任务定义做准备：项目中定义的任务可以直接使用这个默认应用
    # 全局访问：在项目的其他地方，可以通过 from celery import current_app 来获取当前默认的 Celery 应用实例
    # 简化任务装饰器使用：设置默认应用后，你可以直接使用 @task 装饰器，而不需要指定具体的应用实例 @celery_app.task
    celery_app.set_default()
    app.extensions["celery"] = celery_app

    # NOTE: 定义了 6 个定时任务
    # 告诉 Celery 需要导入哪些模块
    # 格式固定：必须是模块路径的字符串列表
    imports = [
        "schedule.clean_embedding_cache_task",
        "schedule.clean_unused_datasets_task",
        "schedule.create_tidb_serverless_task",
        "schedule.update_tidb_serverless_status_task",
        "schedule.clean_messages",
        "schedule.mail_clean_document_notify_task",
    ]
    day = dify_config.CELERY_BEAT_SCHEDULER_TIME
    
    # NOTE: beat_schedule 字典结构
    # beat_schedule = {
    #     "任务名称": {
    #         "task": "模块路径.任务函数名",     # 固定key: "task", 值必须是完整的任务路径
    #         "schedule": 调度表达式,           # 固定key: "schedule", 定义执行频率
    #     },
    # }
    # 调度表达式的两种格式:
    # 1. timedelta 格式（周期性执行）
    # 2. crontab 格式（定时执行）
    beat_schedule = {
        "clean_embedding_cache_task": {
            "task": "schedule.clean_embedding_cache_task.clean_embedding_cache_task",
            "schedule": timedelta(days=day),
        },
        "clean_unused_datasets_task": {
            "task": "schedule.clean_unused_datasets_task.clean_unused_datasets_task",
            "schedule": timedelta(days=day),
        },
        "create_tidb_serverless_task": {
            "task": "schedule.create_tidb_serverless_task.create_tidb_serverless_task",
            "schedule": crontab(minute="0", hour="*"),
        },
        "update_tidb_serverless_status_task": {
            "task": "schedule.update_tidb_serverless_status_task.update_tidb_serverless_status_task",
            "schedule": timedelta(minutes=10),
        },
        "clean_messages": {
            "task": "schedule.clean_messages.clean_messages",
            "schedule": timedelta(days=day),
        },
        # every Monday
        "mail_clean_document_notify_task": {
            "task": "schedule.mail_clean_document_notify_task.mail_clean_document_notify_task",
            "schedule": crontab(minute="0", hour="10", day_of_week="1"),
        },
    }
    # 将配置应用到 Celery 实例，参数名是固定的
    # - beat_schedule: 定时任务配置
    # - imports: 任务模块导入
    celery_app.conf.update(beat_schedule=beat_schedule, imports=imports)

    return celery_app
