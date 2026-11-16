# API 契约

版本0.2。查询使用已发布SQLite的只读内存快照，不在请求中启动Spark。按文件版本更新快照及查询缓存，避免WSL挂载盘随机读取影响交互。

| GET路径 | 参数 | 输出 |
| --- | --- | --- |
| /api/health | 无 | status、data_ready、version |
| /api/metadata | 无 | ETL来源、数量、运行时间、Spark版本/master/application_id |
| /api/filters | 无 | 数据中的month/carrier/origin/dest选项 |
| /api/overview | month、carrier、origin可选 | filters、data、definitions |
| /api/breakdown/{dimension} | 同上 | dimension及各组data |
| /api/dashboard | month/carrier/origin/dest/hour可选 | summary/trend/carriers/airports/heatmap/hours/routes/scope |

month限2024-01至06，origin限三位大写机场码。dimension白名单为month/carrier/origin/dest/weekday/dep_hour。错误参数422，数据尚未生成503，无匹配的合法筛选返回计数0、比例null。仅使用绑定SQL参数；维度白名单后插入SQL。

data含planned/eligible/delayed/cancelled/diverted/arr_delay_sum/arr_delay_count/delay_rate/cancellation_rate/mean_arrival_delay。日期、机场本地时间语义和分母见数据契约。

P3复盘和P4实验接口将在对应里程碑实现，当前不提供占位预测接口。

P2已通过dashboard的routes与hours实现。hour为0至23，dest为三位大写机场码。routes按航班数返回前20条。scope包含实际已发布月份与本次筛选。查询无匹配时各图返回空列表，summary比例为null。已构建前端时后端同时提供根路径静态网页。
