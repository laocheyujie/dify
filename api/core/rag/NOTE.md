## 关键代码

### 关键词检索-词表构建
- 代码片段 jieba-create：
- 代码位置：api/core/rag/datasource/keyword/jieba/jieba.py crete
- 代码逻辑解释：加锁保持操作原子性 ->获取数据集关键词表->提取文本关键词->更新词表->保存

### 关键词召回
- 代码片段 jieba-_retrieve_ids_by_query：
- 代码位置：api/core/rag/datasource/keyword/jieba/jieba.py _retrieve_ids_by_query
- 代码逻辑解释：读取词表->统计命中段落->返回top k