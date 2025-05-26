from configs import dify_config
from dify_app import DifyApp


def init_app(app: DifyApp):
    if dify_config.RESPECT_XFORWARD_HEADERS_ENABLED:
        from werkzeug.middleware.proxy_fix import ProxyFix

        # NOTE: x_port=1 参数，这表示信任第一个 X-Forwarded-Port 头信息
        app.wsgi_app = ProxyFix(app.wsgi_app, x_port=1)  # type: ignore
        """
        NOTE:
        这段代码的主要目的是解决在应用部署在反向代理（如 Nginx）后面时可能出现的请求信息不准确的问题。
        当应用运行在反向代理后面时，原始的客户端信息（如 IP 地址、端口等）会被代理服务器修改，
        而 ProxyFix 中间件可以帮助应用正确识别这些信息。
        可以确保应用能够获取到正确的客户端信息。
        """
