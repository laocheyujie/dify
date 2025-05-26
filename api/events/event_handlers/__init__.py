from .clean_when_dataset_deleted import handle
from .clean_when_document_deleted import handle
from .create_document_index import handle
from .create_installed_app_when_app_created import handle
from .create_site_record_when_app_created import handle
from .deduct_quota_when_message_created import handle
from .delete_tool_parameters_cache_when_sync_draft_workflow import handle
from .update_app_dataset_join_when_app_model_config_updated import handle
from .update_app_dataset_join_when_app_published_workflow_updated import handle
from .update_provider_last_used_at_when_message_created import handle

# NOTE: 事件处理器的组织方式
# 这是一个基于 Blinker 信号系统的事件处理机制，这些 handle 函数实际上是通过装饰器方式被注册为事件监听器的。
# 1. 系统使用了 Blinker 库来实现事件系统，在 events/app_event.py 中定义了各种信号
# 2. 每个事件处理器文件（如 create_installed_app_when_app_created.py）都使用了装饰器来注册事件处理函数 `@app_was_created.connect`
# 3. 在 extensions/ext_import_modules.py 中这些事件处理器被导入时，所有的处理器模块都会被加载，每个模块中的 handle 函数都会通过装饰器自动注册到相应的事件信号上
# 4. 当相应的事件发生时（比如应用创建、文档删除等），这些处理函数就会被自动调用

# 这是一个典型的事件驱动架构设计，通过这种方式实现了系统各个组件之间的解耦。
# 虽然这些 handle 函数看起来没有被直接使用，但它们都是通过事件系统被间接调用的。
