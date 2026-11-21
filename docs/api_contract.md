# API 契约

版本0.3。查询使用已发布SQLite的只读内存快照，不在请求中启动Spark。按文件版本更新快照及查询缓存，避免WSL挂载盘随机读取影响交互。

| GET路径 | 参数 | 输出 |
| --- | --- | --- |
| /api/health | 无 | status、data_ready、version |
| /api/metadata | 无 | ETL来源、数量、运行时间、Spark版本/master/application_id |
| /api/filters | 无 | 数据中的month/carrier/origin/dest选项 |
| /api/overview | month、carrier、origin可选 | filters、data、definitions |
| /api/breakdown/{dimension} | 同上 | dimension及各组data |
| /api/dashboard | month/carrier/origin/dest/hour可选 | summary/trend/carriers/airports/heatmap/hours/comparison_hours/routes/scope |

month限2024-01至06，origin限三位大写机场码。dimension白名单为month/carrier/origin/dest/weekday/dep_hour。错误参数422，数据尚未生成503，无匹配的合法筛选返回计数0、比例null。仅使用绑定SQL参数；维度白名单后插入SQL。

data含planned/eligible/delayed/cancelled/diverted/arr_delay_sum/arr_delay_count/delay_rate/cancellation_rate/mean_arrival_delay。日期、机场本地时间语义和分母见数据契约。

## P3 / P4

| GET路径 | 参数 | 行为 |
| --- | --- | --- |
| /api/experiments | 无 | 真实metrics、verification、error_groups及可用的engineering结果 |
| /api/risk/options | origin、dest、carrier可选 | 从评分库联动查询机场、航司及日期 |
| /api/risk/flights | origin、dest、carrier、date | 返回最多100条已评分真实航班的身份和计划字段 |
| /api/risk/flight/{flight_id} | reveal，默认false | 返回四模型分数、验证集阈值及历史支持数；只有reveal=true才返回actual_delayed |
| /api/risk/examples | 无 | 返回固定20个案例的身份字段，隐藏实际类别 |

flight_id必须是64位十六进制哈希，找不到的ID返回404。date必须是2024年6月的有效日期，格式或范围错误返回422。预测库只读，标签默认不出现在响应中。模型分数属于历史回测，未作独立概率校准。验证产物缺失或未通过时实验接口返回503。

P2已通过dashboard的routes与hours实现。hour为0至23，dest为三位大写机场码。routes按航班数返回前20条。scope包含实际已发布月份与本次筛选。查询无匹配时各图返回空列表，summary比例为null。已构建前端时后端同时提供根路径静态网页。

`comparison_hours` 按当地计划出发小时分组，沿用月份、航司和起降机场筛选，保留全天数据供两时段对照。因此逐小时回放可能无航班，而全天对照仍有有效样本。跨小时先分别求和延误数与有效到达数，再计算比例。分母为零时界面显示“—”。

`/api/experiments` 的 `verification.models[模型].operating_points` 由 `scripts/verify_ml.py` 从导出的六月评分逐条复算，数组包含 0.20、0.35、0.50 三档的 threshold、tp、fp、fn、tn。发布值与正式混淆矩阵来自 `metrics.test[模型]`。旧验证文件缺少演示数组时，模型比较与发布值仍可用。
