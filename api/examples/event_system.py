from blinker import signal
from datetime import datetime


# 定义信号: 分别用于文章发布和通知发送事件
article_published = signal('article-published')
notification_sent = signal('notification-sent')

# 事件处理器
# 使用装饰器 @article_published.connect 注册事件处理器。当事件触发时，这个函数会被自动调用
@article_published.connect
def handle_article_published(sender, **kwargs):
    """当文章发布时，发送通知给订阅者"""
    article = sender
    print(f"1. 处理文章发布事件: {article['title']}")
    # 触发通知事件
    # 使用 send() 方法触发事件，可以传递任意参数
    notification_sent.send(
        article=article,
        subscribers=kwargs.get('subscribers', [])
    )

@notification_sent.connect
def handle_notification_sent(sender, **kwargs):
    """当需要发送通知时，记录通知日志"""
    article = kwargs.get('article')
    subscribers = kwargs.get('subscribers', [])
    print(f"2. 发送通知给 {len(subscribers)} 个订阅者，关于文章: {article['title']}")

# 使用示例
def main():
    # 创建一篇文章
    article = {
        'title': 'Python事件驱动编程',
        'content': '这是一篇关于事件驱动编程的文章...',
        'author': '张三',
        'publish_time': datetime.now()
    }
    
    # 模拟订阅者列表
    subscribers = ['user1@example.com', 'user2@example.com']
    
    # 触发文章发布事件
    # 使用 send() 方法触发事件，可以传递任意参数
    article_published.send(article, subscribers=subscribers)

if __name__ == '__main__':
    main() 