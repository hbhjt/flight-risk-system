# 航空航班延误分析与风险预测系统

基于BTS官方数据、HDFS、Spark、FastAPI和Vue的课程项目。

## 当前进度

方案已定稿：[最终方案](docs/final_plan.md)。六个月3461319条官方记录均已通过HDFS→Spark Standalone→SQLite→API处理与独立数量核对。P1运行驾驶舱和P2航线探索已实现。P3/P4、模型实验与课程材料仍待完成。详见[实施清单](docs/implementation_plan.md)及[M2验收](docs/milestone_m2.md)。

## 环境

已实测WSL2 Ubuntu22.04、Python3.10、Temurin JRE11、Spark3.5.8。Hadoop3.3.6使用单机伪分布式，Spark采用单机Standalone；不是多物理机集群。

代码位于本仓库；运行时默认`D:/flight-risk-runtime`，WSL路径`/mnt/d/flight-risk-runtime`。现有机器使用的WSL名称仅是本机信息，不作为他人的固定前提。Linux用户可通过`FLIGHT_RUNTIME`改到自己的独立目录。

## 数据获取

在仓库根目录使用有requests依赖的Python：

```powershell
python -m ingestion.download --months 2024-01
python -m ingestion.download --months 2024-02 2024-03 2024-04 2024-05 2024-06
```

官方ZIP下载失败时，从BTS目录手动获取Reporting Carrier对应月份，然后运行：

```powershell
python -m ingestion.download --months 2024-01 --import-zip D:/downloads/official-month.zip
```

脚本校验ZIP，保留来源、UTC时间、SHA256、实际表头和行数。原始数据不提交Git。数据源为美国航班，不能解释为中国航班运行情况。

## 独立运行依赖

以下例子使用Windows下载、WSL运行。先在WSL创建独立环境：

```bash
python3 -m venv /mnt/d/flight-risk-runtime/venv
/mnt/d/flight-risk-runtime/venv/bin/python -m pip install -r requirements.lock.txt
```

Windows下载Linux JRE及Hadoop归档：

```powershell
python scripts/bootstrap_downloads.py D:/flight-risk-runtime
```

Apache归档慢时可用镜像，仍强制对照Apache官方SHA512：

```powershell
python scripts/bootstrap_downloads.py D:/flight-risk-runtime --hadoop-url https://mirrors.huaweicloud.com/apache/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
```

在WSL仓库根目录执行：

```bash
bash infrastructure/install.sh
bash scripts/start_cluster.sh
bash scripts/run_etl.sh 2024-01
```

安装只会首次格式化项目自己的全新NameNode目录；不会自动清理HDFS或重新格式化已有元数据。再次安装可复用依赖。单月ETL会替换指定数据库。发布正式半年数据请执行：

```bash
bash scripts/run_all_months.sh
```

该脚本保留六个月独立产物，跳过已有月度作业，并验证月份后原子合并，重复合并不追加重复记录。若需要重新处理某月，显式运行`bash scripts/run_etl.sh 2024-02 artifacts/months/2024-02.sqlite`，再执行`python scripts/merge_months.py`。

## 交互式网页

前端使用Vue3、Vite、ECharts，Node要求见package.json及Vite支持范围，已在Node24实测。Windows仓库根目录：

```powershell
python -m ingestion.map_assets
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
```

地图快照已随仓库保存，正常启动无需重新下载。重新生成时同步检查地图许可和sources.json。前端构建后再启动下方后端，即可在[本地工作台](http://localhost:18000/)使用两个页面。地图与字体不依赖外部CDN。

开发调试可另开终端执行`npm.cmd run dev --prefix frontend`，使用15173端口并将/api代理到18000。正式演示使用后端提供的构建版本，只需一个服务。

## 查询服务

WSL仓库根目录执行：

```bash
/mnt/d/flight-risk-runtime/venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 18000
```

访问[网页](http://localhost:18000/)、[API文档](http://localhost:18000/docs)、[统计接口](http://localhost:18000/api/overview)、[ATL筛选](http://localhost:18000/api/overview?origin=ATL)。数据不存在时统计接口返回503，不生成演示数值。查询库约92MB；服务首次加载内存快照和首次全局聚合可能等待数秒，后续查询按版本缓存。

## 验证与关闭

```bash
source infrastructure/runtime.sh
python -m pytest -q
FLIGHT_SPARK_TESTS=1 python -m pytest -q
python scripts/verify_all.py
bash scripts/stop_cluster.sh
```

第二条测试命令需要Java，验证合成边界用例；真实统计由正式ETL生成。作业日志位于`logs`、质量报告和SQLite位于`artifacts`，默认不提交。运行模式、Spark master和application_id写入报告。

## GitHub与许可

代码、方案、测试和依赖锁定文件适合版本管理。数据、日志、数据库、运行环境和密钥由`.gitignore`排除。公开结果将另行导出脱敏的小型摘要。教师原始文件与个人课程信息不进入仓库。

目前没有指定开源许可证；上传GitHub与授予开源许可是两件事。数据和地图素材的来源与许可单独记录。不提交密码或令牌。发布前确认仓库名称、可见性及暂存文件。
