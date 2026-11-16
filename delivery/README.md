# 课程交付材料

- flight-risk-report.pdf：12页报告，覆盖需求、架构、技术、过程、结果、问题和总结。
- report-source.md：报告文字与表格源稿，支持后续修改。图片路径指向docs/images。
- flight-risk-defense.pptx：15页可编辑答辩PPT，模型/数据/工程表格均为原生可编辑表格。
- flight-risk-demo.mp4：真实系统68.44秒录屏，1366×768，无配音。
- defense-notes.md：逐页讲解重点、视频配合说明和答辩问题。

封面和贡献页尚需补齐真实组名、成员姓名/学号/班级与实际分工。老师要求各成员按实际承担部分讲解，当前无配音录屏不代替本人讲解。课程材料第16周提交，具体日期以教师通知为准。报告格式没有硬性限定，本版采用PDF，另保留可编辑文字源稿。

## 本机演示

WSL项目根目录执行 `bash scripts/start_demo.sh`，浏览器打开 http://localhost:18000/ 。Windows可在项目根目录执行 `powershell -File scripts/start_demo.ps1`。需要默认WSL发行版拥有README中的独立Python依赖，且本地数据库和frontend/dist已生成。若端口已有项目服务直接访问，不要重复启动。

演示仅使用已发布数据与评分，HDFS和Spark可以关闭。重新处理数据、训练或格式实验需要按主README启动集群。

## 打包

在独立环境运行 `python scripts/package_delivery.py`，生成代码及材料包。追加 `--with-data` 生成带已发布SQLite及构建前端的本机离线演示包，不包含原始ZIP、HDFS块、运行环境或密钥。带数据的包保存在本地，不提交GitHub。

代码包供阅读和按README复现；演示包无需重跑ETL与训练，但仍需要Python依赖。它们不等同于免安装的Windows可执行程序。ZIP中的package-manifest.json记录文件SHA256和打包时的源代码提交。

GitHub为私有仓库 https://github.com/hbhjt/flight-risk-system 。仓库上传与向教师正式提交相互独立。
