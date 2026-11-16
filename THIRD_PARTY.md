# 数据与地图来源

- 航班：美国BTS Reporting Carrier On-Time Performance，https://www.transtats.bts.gov/PREZIP/ 。原始文件不纳入Git，使用下载脚本获取，逐月记录来源和SHA256。
- 机场坐标：OurAirports维护者的公开仓库，https://github.com/davidmegginson/ourairports-data 。源许可为Unlicense，原文随frontend/public/maps/ourairports-license.txt保存。派生JSON保留美国及相关属地的IATA代码和必要坐标字段。
- 本土地理边界：Natural Earth，https://www.naturalearthdata.com/ ，源文件来自维护者仓库https://github.com/nvkelso/natural-earth-vector 。公共领域条款：https://www.naturalearthdata.com/about/terms-of-use/ 。派生文件选取美国本土49个州/特区要素。

地图抓取时间、源链接和原始哈希见frontend/public/maps/sources.json。坐标用于历史可视化，快照不代表2024年的机场名称或代码状态；无匹配坐标的BTS机场仍保留统计。地理底图不代表实际航迹。

Vue、Vite和ECharts等软件依赖以各自发布的许可为准，版本锁定于frontend/package-lock.json。上述数据及第三方软件许可不等于本项目代码已经获得用户指定的开源许可证。
