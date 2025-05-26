from configs import dify_config
from dify_app import DifyApp


def init_app(app: DifyApp):
    if dify_config.SENTRY_DSN:
        import openai
        import sentry_sdk
        from langfuse import parse_error  # type: ignore
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.flask import FlaskIntegration
        from werkzeug.exceptions import HTTPException

        from core.model_runtime.errors.invoke import InvokeRateLimitError

        def before_send(event, hint):
            # NOTE: 回调函数，用于在发送错误到 Sentry 之前进行过滤
            if "exc_info" in hint:
                exc_type, exc_value, tb = hint["exc_info"]
                # 如果错误信息中包含 defaultErrorResponse，则不会发送到 Sentry
                if parse_error.defaultErrorResponse in str(exc_value):
                    return None

            return event

        sentry_sdk.init(
            dsn=dify_config.SENTRY_DSN,
            integrations=[FlaskIntegration(), CeleryIntegration()],
            # 错误忽略列表
            ignore_errors=[
                HTTPException,
                ValueError,
                FileNotFoundError,
                openai.APIStatusError,
                InvokeRateLimitError,
                parse_error.defaultErrorResponse,
            ],
            traces_sample_rate=dify_config.SENTRY_TRACES_SAMPLE_RATE,                  # 追踪采样率
            profiles_sample_rate=dify_config.SENTRY_PROFILES_SAMPLE_RATE,              # 性能分析采样率
            environment=dify_config.DEPLOY_ENV,                                        # 部署环境
            release=f"dify-{dify_config.CURRENT_VERSION}-{dify_config.COMMIT_SHA}",    # 版本信息
            before_send=before_send,
        )
