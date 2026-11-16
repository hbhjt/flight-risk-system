# 数据契约

正式表：BTS Reporting Carrier On-Time Performance，2024-01至06。官方字段定义以 https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ 为准。

## 实际样本

已获取2024-01，547271条记录，ZIP 27573265字节，解压CSV 246830488字节。ZIP SHA256为 fe089b45523f9d4ac0ccd0e176a543d274e914ee5ae5bd384dbaafc7dc06ebfd。CSV表头包含109个具名字段及一个尾部空字段。清洗忽略空列，原始文件保持不变。下载日期、表头及CSV哈希保存于被Git忽略的data/raw/manifests。

## 清洗字段

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| FlightDate | date | 从实际日期字符串前10位解析；无法解析隔离 |
| Reporting_Airline / Origin / Dest | string | 不能为空；保留官方编码 |
| Flight_Number_Reporting_Airline | string | 必须存在，用于业务键检查 |
| CRSDepTime / CRSArrTime | integer HHMM | 2400映射小时0；非法分钟不进入小时分组 |
| DayOfWeek | integer | 官方星期编码，1至7 |
| Distance / CRSElapsedTime | double | 英里/分钟；模型前另检查非负与缺失 |
| Cancelled / Diverted | double | 必须为0或1，否则状态隔离 |
| ArrDel15 | double | 非取消非备降且0/1才可作为二分类标签 |
| ArrDelay | double | 到达分钟差，保留负数；缺失不计入均值分母 |

互斥状态优先级：invalid_key_or_status → cancelled → diverted → arrival_valid → arrival_label_missing。取消与备降同时为1的异常需在全量质量检查中另报告；目前互斥归类优先取消。原始完全重复先去除，再检查业务键冲突；存在冲突时中止发布并调查。

## 应用聚合

粒度：month × carrier × origin × dest × weekday × dep_hour。保存 planned、eligible、delayed、cancelled、diverted、arr_delay_sum、arr_delay_count。API汇总这些可加量后计算率与均值。空分母返回null，前端显示无有效样本，不能显示0%。

单月ETL默认替换指定应用数据库。正式半年发布使用run_all_months.sh将月度产物分别保存，再由merge_months.py验证六个月范围并原子合并。重复合并不追加重复记录，旧发布数据在新版本完成前保持可查询。

## 模型契约

遵循final_plan.md的预热/训练/验证/测试与快照。状态列仅用于筛选和标签，不进入特征。生成历史表时保存feature_cutoff_month，通过自动测试阻止同月或未来标签进入。模型样本还必须满足计划特征完整且有效，并独立披露过滤数量。
