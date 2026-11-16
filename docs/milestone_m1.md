# 首次真实数据闭环验收

验收日期2026-11-16。范围为2024年1月完整官方Reporting Carrier数据，其他月份已下载但未进入本次统计。完整系统尚未完成。

## 实际执行

WSL仓库根目录执行`bash scripts/start_cluster.sh`和`bash scripts/run_etl.sh 2024-01`。输入为`hdfs://127.0.0.1:19000/flight-risk/raw/2024-01/flights.csv`，输出位于`/flight-risk/runs/2024-01`的silver和gold目录。

Spark版本3.5.8，master为`spark://127.0.0.1:17077`，application_id为`app-20261116054417-0000`。同机1个Master、1个Worker、1个HDFS DataNode，执行器2核/1GB，driver1GB。作业注册于05:44:17（纽约时间），报告生成于10:45:34 UTC。该间隔包含执行器启动和处理，不作为正式性能实验结果。

## 结果

| 项目 | 实际值 |
| --- | ---: |
| 原始记录 | 547271 |
| 完全重复 | 0 |
| 业务键冲突组 | 0 |
| 有效到达标签 | 525370 |
| 取消 | 20389 |
| 备降 | 1512 |
| 到达延误至少15分钟 | 126410 |
| 到达分钟差总和 | 5438787 |
| 延误率 | 24.0611% |
| 取消率 | 3.7256% |
| 平均有符号到达延误 | 10.3523分钟 |

三个互斥有效状态计数之和为原始记录数。独立Python CSV流式核对与SQLite聚合的全部计数、分钟差总和一致。

## 验证证据

- 隔离Linux环境执行`FLIGHT_SPARK_TESTS=1 python -m pytest -q`，5项通过，1条依赖弃用提示。
- 实际HTTP请求`/api/health`、`/api/overview`、`/api/overview?origin=ATL`和`/api/metadata`均200；ATL样本为26315，运行模式核对为Standalone。
- HDFS进程经历停止后重启，原始文件及silver/gold结果仍可读取；不重新格式化NameNode。
- HDFS启动从原启动会话脱离，修复WSL命令结束后SIGHUP导致服务退出的问题。
- 本地完整日志、质量报告、HTTP响应、独立核对JSON、HDFS目录清单和Spark事件日志保留于被Git忽略的logs、artifacts及独立运行目录。此文仅保存适合版本管理的验收摘要。

## 已下载月份

2024-01：547271；02：519221；03：591767；04：582185；05：609743；06：611132。合计3461319条。来源、哈希、实际表头逐月记录在data/raw/manifests。

## 待完成

六个月合并发布、四个可视化页面、B0至B3实验、防泄漏测试、CSV/Parquet公平对照、课程报告/PPT/视频。上述内容没有被本次M1验收替代。
