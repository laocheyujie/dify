import os
import sys

# cdg:源码启动API示例：uv run flask run --host 0.0.0.0 --port=5001 --debug
def is_db_command():
    if len(sys.argv) > 1 and sys.argv[0].endswith("flask") and sys.argv[1] == "db":
        return True
    return False


# create app
if is_db_command():
    from app_factory import create_migrations_app

    app = create_migrations_app()
else:
    # It seems that JetBrains Python debugger does not work well with gevent,
    # so we need to disable gevent in debug mode.
    # If you are using debugpy and set GEVENT_SUPPORT=True, you can debug with gevent.
    if (flask_debug := os.environ.get("FLASK_DEBUG", "0")) and flask_debug.lower() in {"false", "0", "no"}:
        from gevent import monkey  # type: ignore

        # gevent
        # cdg:在使用 gevent 库的时候，一般会在代码开头的地方执行gevent.monkey.patch_all()，
        # 这行代码的作用是把标准库中的socket模块给替换掉，这样我们在使用socket的时候，
        # 不用修改任何代码就可以实现对代码的协程化，达到提升性能的目的。
        monkey.patch_all()

        from grpc.experimental import gevent as grpc_gevent  # type: ignore

        # grpc gevent
        grpc_gevent.init_gevent()
        # cdg:初始化gevent，使得gRPC可以在gevent的协程环境中运行。
        # gevent是一个基于协程的Python网络库，能够实现高并发的网络应用。
        # 通过初始化，gRPC可以利用gevent的异步特性来处理并发请求，提高性能。

        # cdg:psycogreen是一个用于将psycopg（一个流行的PostgreSQL数据库适配器）与gevent协程库结合使用的库。
        import psycogreen.gevent  # type: ignore

        # cdg:以下一行代码的作用是对psycopg进行补丁处理，使其能够与gevent 协同工作。通过打补丁，psycopg 的阻塞操作（如数据库查询）将被转换为非阻塞操作，从而允许其他协程在等待数据库响应时继续执行。这使得在使用 gevent 的应用程序中，数据库操作不会阻塞整个事件循环，从而提高了并发性能。
        psycogreen.gevent.patch_psycopg()

    from app_factory import create_app

    app = create_app()
    # cdg:从app的extensions属性中获取名为"celery"的扩展，并将其赋值给变量celery。
    # 在Flask中，extensions是一个字典，用于存储与应用相关的扩展（如Celery、SQLAlchemy 等）,
    # 通过这种方式，可以方便地访问和使用与Flask应用集成的Celery实例，以便进行异步任务处理。
    celery = app.extensions["celery"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
