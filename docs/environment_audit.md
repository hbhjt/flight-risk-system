# 环境审计

检查日期：2026-11-16。

| 项目 | 实际结果 |
| --- | --- |
| Windows | Windows11家庭版中文，Intel i7-14650HX，24逻辑核 |
| 内存 | 15.8GB；初检空闲约2.3GB，运行时会变化 |
| 磁盘 | C盘约24GB可用，D盘约305GB可用 |
| Windows Python | Anaconda Python3.12.3，不向其全局环境安装项目依赖 |
| Windows Java/Node | Java17.0.9，Node24.20.0 |
| Docker | 未在PATH发现，不将Docker视为已可用 |
| WSL | 已有Ubuntu22.04，Python3.10.12；初检无Java/HDFS/Spark |
| WSL资源 | 可见约7.8GB内存，2GB swap，初检空闲约7.3GB |
| 本地Git | 可用，仓库已在本项目目录初始化 |
| GitHub | 已通过连接验证账号hbhjt；尚未确定目标仓库和可见性，未发布 |

## 隔离策略

代码位于D:/大数据/flight-risk-system。项目运行依赖和HDFS块位于D:/flight-risk-runtime。WSL内部对应/mnt/d路径。独立venv已创建，实际安装JRE11.0.33、Hadoop3.3.6、PySpark3.5.8，传递依赖锁定在requirements.lock.txt。HDFS与Standalone主链通过，未改动现有研究环境。

只绑定本机接口及项目专用端口：HDFS RPC19000、NameNode19870、DataNode19864/19866/19867、Spark17077/18080/18081、作业UI14040。服务仅用于本地实验，不作为公网服务。

网络已实际获取六个月BTS ZIP并完成CRC/行数检查。Hadoop归档经镜像获取，与Apache官方SHA512一致。JRE从Adoptium获取，下载来源与本地哈希记录在隔离运行目录downloads.json中。WSL提示现有localhost代理未镜像，直接公网访问可用，未修改WSL全局网络配置。

安装中处理的真实问题：PySpark的PyPI包不包含start-master/start-worker脚本，改为使用spark-class启动Master/Worker；Spark堆大小通过SPARK_DAEMON_MEMORY设置；NTFS小文件解压较慢，跳过归档内HTML文档，保留全部运行库。所有项目服务只用专属端口。
