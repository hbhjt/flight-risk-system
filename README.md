# 航空航班延误分析与风险预测系统

基于BTS官方数据、HDFS、Spark、FastAPI和Vue的课程项目。

## 当前进度

方案已定稿：[最终方案](docs/final_plan.md)。六个月3461319条官方记录均已通过HDFS→Spark Standalone→SQLite→API处理与独立数量核对。四个页面、B0至B3真实模型实验及CSV/Parquet格式实验均已实现。报告、PPT、真实录屏和讲解稿已生成，待补真实成员信息。详见[实施清单](docs/implementation_plan.md)及[M2验收](docs/milestone_m2.md)。

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

前端使用Vue3、Vite、ECharts，Node要求见package.json及Vite支持范围，已在Node22.14和Node24实测。Windows仓库根目录：

```powershell
python -m ingestion.map_assets
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
```

地图快照已随仓库保存，正常启动无需重新下载。重新生成时同步检查地图许可和sources.json。前端构建后再启动下方后端，即可在[本地工作台](http://localhost:18000/)使用四个页面。地图与字体不依赖外部CDN。

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

## M3 模型实验

B0至B3已完成，详见[模型验收](docs/milestone_m3.md)和[实验协议](docs/m3_protocol.md)。六月601272条评分保存在artifacts/predictions.sqlite，小型结果在results/m3。P3风险复盘和P4实验验证已接入。

复现时先启动集群，再依次运行：

```bash
bash scripts/run_ml.sh prepare
bash scripts/run_ml.sh pilot
bash scripts/run_ml.sh formal
bash scripts/run_ml.sh export
python scripts/verify_ml.py
python scripts/report_m3.py
```

formal复用同配置已完成候选；更改实验配置应使用新版本。绘图脚本scripts/plot_m3.py使用Matplotlib，可选输出PNG/SVG，不参与模型训练。

## M4 集成与工程实验

四个页面分别提供全局驾驶舱、航线与时段探索、六月真实航班风险复盘、模型与存储格式实验。P3默认隐藏实际结果，点击后才展开；只支持已评分的六月真实航班，不接受任意虚构航班。P4可切换模型的可靠性图和混淆矩阵。

```bash
bash scripts/run_benchmark.sh
```

真实三轮CSV查询中位数1.7755秒，Parquet为0.7055秒。两者均为相同5列、相同3461319行、相同9327组聚合，结果SHA256一致。该实验只清除Spark缓存，未清除操作系统/HDFS缓存，存储字节数也不等于查询扫描字节数。详见[集成验收](docs/milestone_m4.md)、[原始实验记录](results/engineering/benchmark.json)及[API契约](docs/api_contract.md)。

后端无需在线启动Spark即可演示已发布的数据与评分；重新生成数据、训练模型或重跑格式实验时需要启动集群。

## 现场演示

1. 打开运行驾驶舱，机场简报按延误班次排名。选择六月，点击 DFW 进入航线探索，再选 LAX。上午延误 52/193 班，晚间 96/199 班，相差 21.3 个百分点。可切换比较时段或回放单个小时。
2. 在风险复盘中选择六月已评分航班。先看分数，再展开真实标签，核对命中、误报、漏报或正确排除。
3. 在实验验证中选 B3，比较发布阈值和演示值 20%。同一测试集上，误报减少 95,068 班，漏报增加 29,134 班。再查看同深度特征验证与相同输入的存储格式对照。

[航线界面](docs/images/brief-route.jpg) · [阈值推演界面](docs/images/brief-threshold.jpg) · [带字幕演示](delivery/flight-risk-demo.mp4) · [答辩操作与口径](delivery/defense-notes.md)

## 课程交付材料

[交付目录](delivery/README.md)包含12页报告、15页可编辑PPT、真实无配音视频和讲解稿。封面与贡献页需填写实际组员资料，不应直接把空白版本作为最终个人提交。启动已发布演示：`bash scripts/start_demo.sh`，Windows可运行`scripts/start_demo.ps1`。

代码与材料打包：`python scripts/package_delivery.py`；包含本地已发布数据库与前端构建的演示包：`python scripts/package_delivery.py --with-data`。两种ZIP均不提交GitHub，包内含文件清单和校验和。

当前代码和交付材料已推送并通过远程main提交SHA核验。远程仓库为[hbhjt/flight-risk-system](https://github.com/hbhjt/flight-risk-system)，私有可见性。材料、代码和小型实验结果可随仓库更新，原始数据、模型大文件和数据库仍被忽略。
