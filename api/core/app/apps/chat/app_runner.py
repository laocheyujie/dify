import logging
from typing import cast

from core.app.apps.base_app_queue_manager import AppQueueManager, PublishFrom
from core.app.apps.base_app_runner import AppRunner
from core.app.apps.chat.app_config_manager import ChatAppConfig
from core.app.entities.app_invoke_entities import (
    ChatAppGenerateEntity,
)
from core.app.entities.queue_entities import QueueAnnotationReplyEvent
from core.callback_handler.index_tool_callback_handler import DatasetIndexToolCallbackHandler
from core.memory.token_buffer_memory import TokenBufferMemory
from core.model_manager import ModelInstance
from core.model_runtime.entities.message_entities import ImagePromptMessageContent
from core.moderation.base import ModerationError
from core.rag.retrieval.dataset_retrieval import DatasetRetrieval
from extensions.ext_database import db
from models.model import App, Conversation, Message

logger = logging.getLogger(__name__)


class ChatAppRunner(AppRunner):
    """
    Chat Application Runner
    """

    def run(
        self,
        application_generate_entity: ChatAppGenerateEntity,
        queue_manager: AppQueueManager,
        conversation: Conversation,
        message: Message,
    ) -> None:
        """
        Run application
        :param application_generate_entity: application generate entity
        :param queue_manager: application queue manager
        :param conversation: conversation
        :param message: message
        :return:
        """
        app_config = application_generate_entity.app_config
        app_config = cast(ChatAppConfig, app_config)

        app_record = db.session.query(App).filter(App.id == app_config.app_id).first()
        if not app_record:
            raise ValueError("App not found")

        inputs = application_generate_entity.inputs
        query = application_generate_entity.query
        files = application_generate_entity.files

        image_detail_config = (
            application_generate_entity.file_upload_config.image_config.detail
            if (
                application_generate_entity.file_upload_config
                and application_generate_entity.file_upload_config.image_config
            )
            else None
        )
        image_detail_config = image_detail_config or ImagePromptMessageContent.DETAIL.LOW

        memory = None
        if application_generate_entity.conversation_id:
            # get memory of conversation (read-only)
            # NOTE: 2.5.1 读取历史对话信息（如果存在）
            model_instance = ModelInstance(
                provider_model_bundle=application_generate_entity.model_conf.provider_model_bundle,
                model=application_generate_entity.model_conf.model,
            )

            memory = TokenBufferMemory(conversation=conversation, model_instance=model_instance)

        # organize all inputs and template to prompt messages
        # Include: prompt template, inputs, query(optional), files(optional)
        #          memory(optional)
        # NOTE: 2.5.2 组织完整的 prompt
        prompt_messages, stop = self.organize_prompt_messages(
            app_record=app_record,
            model_config=application_generate_entity.model_conf,
            prompt_template_entity=app_config.prompt_template,
            inputs=inputs,
            files=files,
            query=query,
            memory=memory,
            image_detail_config=image_detail_config,
        )

        # moderation
        # NOTE: 2.5.3 对输入进行安全审核（方式为关键词、API、Openai服务，用户选择）
        try:
            # process sensitive_word_avoidance
            _, inputs, query = self.moderation_for_inputs(
                app_id=app_record.id,
                tenant_id=app_config.tenant_id,
                app_generate_entity=application_generate_entity,
                inputs=inputs,
                query=query,
                message_id=message.id,
            )
        except ModerationError as e:
            self.direct_output(
                queue_manager=queue_manager,
                app_generate_entity=application_generate_entity,
                prompt_messages=prompt_messages,
                text=str(e),
                stream=application_generate_entity.stream,
            )
            return

        if query:
            # annotation reply
            # NOTE: 2.5.4 如果开启标注回复，则通过 AnnotationReplyFeature 从数据库中查询答案，并跳到handle response那一步
            annotation_reply = self.query_app_annotations_to_reply(
                app_record=app_record,
                message=message,
                query=query,
                user_id=application_generate_entity.user_id,
                invoke_from=application_generate_entity.invoke_from,
            )

            if annotation_reply:
                queue_manager.publish(
                    QueueAnnotationReplyEvent(message_annotation_id=annotation_reply.id),
                    PublishFrom.APPLICATION_MANAGER,
                )

                self.direct_output(
                    queue_manager=queue_manager,
                    app_generate_entity=application_generate_entity,
                    prompt_messages=prompt_messages,
                    text=annotation_reply.content,
                    stream=application_generate_entity.stream,
                )
                return

        # fill in variable inputs from external data tools if exists
        external_data_tools = app_config.external_data_variables
        if external_data_tools:
            # NOTE: 2.5.5 如果存在外部数据工具，则通过线程池并发获取数据
            inputs = self.fill_in_inputs_from_external_data_tools(
                tenant_id=app_record.tenant_id,
                app_id=app_record.id,
                external_data_tools=external_data_tools,
                inputs=inputs,
                query=query,
            )

        # get context from datasets
        context = None
        # NOTE: 2.5.6 如果启用了数据库，则通过DatasetRetrieval进行内容召回
        if app_config.dataset and app_config.dataset.dataset_ids:
            hit_callback = DatasetIndexToolCallbackHandler(
                queue_manager,
                app_record.id,
                message.id,
                application_generate_entity.user_id,
                application_generate_entity.invoke_from,
            )

            dataset_retrieval = DatasetRetrieval(application_generate_entity)
            context = dataset_retrieval.retrieve(
                app_id=app_record.id,
                user_id=application_generate_entity.user_id,
                tenant_id=app_record.tenant_id,
                model_config=application_generate_entity.model_conf,
                config=app_config.dataset,
                query=query,
                invoke_from=application_generate_entity.invoke_from,
                show_retrieve_source=app_config.additional_features.show_retrieve_source,
                hit_callback=hit_callback,
                memory=memory,
                message_id=message.id,
                inputs=inputs,
            )

        # reorganize all inputs and template to prompt messages
        # Include: prompt template, inputs, query(optional), files(optional)
        #          memory(optional), external data, dataset context(optional)
        # NOTE: 2.5.7 再次组织 prompt（prompt template, inputs, query，memory, external data, dataset context）
        prompt_messages, stop = self.organize_prompt_messages(
            app_record=app_record,
            model_config=application_generate_entity.model_conf,
            prompt_template_entity=app_config.prompt_template,
            inputs=inputs,
            files=files,
            query=query,
            context=context,
            memory=memory,
            image_detail_config=image_detail_config,
        )

        # check hosting moderation
        # NOTE: 2.5.8 内容审核（text-moderation-stable）
        hosting_moderation_result = self.check_hosting_moderation(
            application_generate_entity=application_generate_entity,
            queue_manager=queue_manager,
            prompt_messages=prompt_messages,
        )

        if hosting_moderation_result:
            return

        # Re-calculate the max tokens if sum(prompt_token +  max_tokens) over model token limit
        # NOTE: 2.5.9 再次计算tokens是否满足要求
        self.recalc_llm_max_tokens(model_config=application_generate_entity.model_conf, prompt_messages=prompt_messages)

        # Invoke model
        # NOTE: 2.5.10 实例化LLM，将LLM结果包成对应 Event 并放进 queue_manager
        model_instance = ModelInstance(
            provider_model_bundle=application_generate_entity.model_conf.provider_model_bundle,
            model=application_generate_entity.model_conf.model,
        )

        db.session.close()

        invoke_result = model_instance.invoke_llm(
            prompt_messages=prompt_messages,
            model_parameters=application_generate_entity.model_conf.parameters,
            stop=stop,
            stream=application_generate_entity.stream,
            user=application_generate_entity.user_id,
        )

        # handle invoke result
        self._handle_invoke_result(
            invoke_result=invoke_result, queue_manager=queue_manager, stream=application_generate_entity.stream
        )
