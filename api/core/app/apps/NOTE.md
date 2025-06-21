## Workflow
核心模块。
1. 读取配置信息
2. 初始化trace_manager，用于跟踪任务
3. 初始化application_generate_entity ，用于存放运行所需要的信息
4. 初始化queue_manager，通过队列传输线程中的结果
5. 启动线程，调用_generate_worker
a. 根据节点信息构建graph
b. 依次运行各节点，把结果包成对应Event并放进queue_manager
6. 调用_handle_response
7. 通过WorkflowAppGenerateTaskPipeline，依次从queue_manager中取出事件并根据这些事件生成相应的流响应


## Chat
1. 读取配置信息
2. 初始化trace_manager，用于跟踪任务
3. 初始化application_generate_entity ，用于存放运行所需要的信息
4. 初始化queue_manager，通过队列传输线程中的结果
5. 启动线程，调用_generate_worker
    1. 读取历史对话信息（如果存在）
    2. 组织完整的prompt
    3. 对输入进行安全审核（方式为关键词、API、Openai服务，用户选择）
    4. 如果开启标注回复，则通过AnnotationReplyFeature从数据库中查询答案，并跳到handle response那一步
    5. 如果存在外部数据工具，则通过线程池并发获取数据
    6. 如果启用了数据库，则通过DatasetRetrieval进行内容召回
    7. 再次组织prompt（prompt template, inputs, query，memory, external data, dataset context）
    8. 内容审核（text-moderation-stable）
    9. 再次计算tokens是否满足要求
    10. 实例化LLM，将LLM结果包成对应Event并放进queue_manager
6. 调用_handle_response


## README
关于 Dify 应用中 App Runner（应用运行器）和 Task Pipeline（任务管道） 的数据库连接管理指南。

### 核心问题

文档首先指出了一个问题：

1.  **存在长耗时任务**：在 `App Runner` 中，执行一次应用会包含一些耗时很长的操作，比如调用大语言模型（LLM）生成内容或请求外部 API。
2.  **数据库连接被长时间占用**：Dify 使用的 `Flask-Sqlalchemy` 框架，其默认策略是“一个 Web 请求（request）从头到尾占用一个数据库连接”。
3.  **导致连接池耗尽**：这就意味着，即使在执行调用 LLM 这种和数据库无关的长耗时任务时，数据库连接也一直被占着不释放。当并发请求增多时，所有可用的数据库连接都会被这些长任务迅速占满，导致新的请求无法获取连接，从而引发错误或服务无响应。

### 解决方案和核心原则

为了解决这个问题，文档规定了一条核心原则：

**在 `App Runner` 和 `Task Pipeline` 中，数据库操作完成后必须立即关闭连接（`db.session.close()`），以将其释放回连接池。**

此外，还有一个最佳实践：**在任务之间最好传递对象的 ID，而不是完整的数据库模型对象（Model Object）**，以避免在 session 关闭后操作对象导致的 "detach errors"（对象游离错误）。

### 代码示例解读

文档给出了三个例子来演示如何实践这个原则：

1.  **创建新记录**:
    *   先执行 `add` 和 `commit` 将数据存入数据库。
    *   关键一步是 `db.session.refresh(app)`，它的作用是把数据库自动生成的一些默认值（比如 `created_at` 时间戳）重新加载到 `app` 这个 Python 对象上。
    *   然后**立即 `db.session.close()` 关闭连接**。
    *   最后返回新记录的 `id`，而不是 `app` 对象本身。

2.  **查询记录**:
    *   通过 `query` 查到 `app` 对象。
    *   **在关闭连接前**，把需要用到的数据（比如 `created_at`）从 `app` 对象中取出来，存到普通变量里。
    *   **立即 `db.session.close()` 关闭连接**。
    *   之后，你就可以拿着取出来的数据（`created_at`）去执行包括长耗时任务在内的后续操作了。

3.  **更新字段**:
    *   先通过 `query` 查到 `app` 对象。
    *   修改对象的属性，然后 `commit` 提交更改。
    *   **立即 `db.session.close()` 关闭连接**。

### 总结

简单来说，这份 `README` 的核心思想就是：**数据库连接是宝贵且有限的资源，不能长时间被无效占用。因此，每次与数据库交互后，都应该“用完即走”，立刻释放连接，确保在高并发下系统的稳定性和可用性。**
