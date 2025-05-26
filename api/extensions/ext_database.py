from dify_app import DifyApp
from models import db


def init_app(app: DifyApp):
    # NOTE: 初始化数据库，会把app的配置读取到db中
    # 当 db.init_app(app) 被调用时，SQLAlchemy 会自动从 Flask 应用的配置中读取 SQLALCHEMY_DATABASE_URI 和 SQLALCHEMY_ENGINE_OPTIONS 来建立数据库连接
    db.init_app(app)
