# API 契约

版本0.1。查询只读SQLite，不在请求中启动Spark。

| GET路径 | 参数 | 输出 |
| --- | --- | --- |
| /api/health | 无 | status、data_ready、version |
| /api/metadata | 无 | ETL来源、数量、运行时间、Spark版本/master/application_id |
| /api/filters | 无 | 数据中的month/carrier/origin/dest选项 |
| /api/overview | month、carrier、origin可选 | filters、data、definitions |
| /api/breakdown/{dimension} | 同上 | dimension及各组data |

month限2024-01至06，origin限三位大写机场码。dimension白名单为month/carrier/origin/dest/weekday/dep_hour。错误参数422，数据尚未生成503，无匹配的合法筛选返回计数0、比例null。仅使用绑定SQL参数；维度白名单后插入SQL。

data含planned/eligible/delayed/cancelled/diverted/arr_delay_sum/arr_delay_count/delay_rate/cancellation_rate/mean_arrival_delay。日期、机场本地时间语义和分母见数据契约。

P2航线、P3复盘和P4实验接口将在对应里程碑实现，当前不提供占位预测接口。
