from events.dataset_event import dataset_was_deleted
from tasks.clean_dataset_task import clean_dataset_task


@dataset_was_deleted.connect
def handle(sender, **kwargs):
    dataset = sender
    # NOTE: 对于关联的数据库、存储图像的 Storage等，全部删除掉
    clean_dataset_task.delay(
        dataset.id,
        dataset.tenant_id,
        dataset.indexing_technique,
        dataset.index_struct,
        dataset.collection_binding_id,
        dataset.doc_form,
    )
