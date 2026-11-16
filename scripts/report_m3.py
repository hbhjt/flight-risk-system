"""Render a factual milestone report only after final metrics and verification exist."""
import json
from pathlib import Path


def main():
    result = json.loads(Path("results/m3/metrics.json").read_text(encoding="utf-8"))
    verified = json.loads(Path("results/m3/verification.json").read_text(encoding="utf-8"))
    if not verified["passed"]:
        raise ValueError("Independent verification must pass before reporting completion")
    selected = result["selection"]["selected"]
    delta = result["b3_minus_b2_pr_auc"]
    conclusion = "B3在本次测试划分的主指标高于B2" if delta > 0 else "B3在本次测试划分未优于B2"
    lines = ["# M3 模型实验验收", "", f"完成时间（UTC）：{result['finished_at_utc']}。配置版本{result['version']}，SHA256为{result['config_sha256']}。", "",
             f"{conclusion}，PR-AUC绝对差为{delta:+.6f}。该结论限于一个半年划分和随机种子42，不表示统计显著性、跨年份泛化或因果机制。", "",
             "## 数据与防泄漏", "", "1月预热，2—4月训练，5月验证，6月测试。5—6月历史均冻结为1—4月。类别编码器只拟合训练期；修改未来标签的合成测试和真实数据的快照一致性检查通过。", "",
             "| 月份 | 模型样本 | 延误标签 | 历史截止 |", "| --- | ---: | ---: | --- |"]
    for row in result["feature_audit"]["snapshots"]:
        lines.append(f"| {row['month']} | {row['count']} | {row['positives']} | {row['history_cutoff_month']} |")
    excluded = sum(row["count"] for row in result["feature_audit"]["quality"] if not row["model_eligible"])
    lines += ["", f"计划输入检查额外排除{excluded}条。B0使用2—4月历史率及预设支持数回退；B3历史包括1月预热。未知类别保留独立编码，不用验证或测试数据拟合字典。", "",
              "## 冻结选择", "", "| 模型 | 选中候选 | 验证PR-AUC | 验证阈值 |", "| --- | ---: | ---: | ---: |"]
    for code, trial in selected.items():
        lines.append(f"| {code} | {trial['candidate']} | {trial['validation']['pr_auc']:.6f} | {trial['validation']['threshold']:.8f} |")
    lines += ["", f"后续演示默认模型按验证PR-AUC预先选择为{result['selection']['recommended_model']}，没有使用测试指标挑选。阈值在验证集按F1选择，测试不调参。", "",
              "## 六月统一测试", "", "| 模型 | PR-AUC | AP | ROC-AUC | Precision | Recall | F1 | Brier |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for code, value in result["test"].items():
        lines.append("| " + code + " | " + " | ".join(f"{value[key]:.6f}" for key in ["pr_auc", "average_precision", "roc_auc", "precision", "recall", "f1", "brier"]) + " |")
    lines += ["", "主PR-AUC用完整precision-recall曲线梯形积分；AP采用阶梯积分，二者分列。PR展示点抽样不改变面积计算。Brier越低越好。分类指标依赖各自验证集阈值，不能当作统一业务成本下的收益。", "",
              "## 相同参数配对验证", "", "| RF候选 | B2验证PR-AUC | B3验证PR-AUC | B3减B2 |", "| --- | ---: | ---: | ---: |"]
    for index in range(2):
        pair = {t["model"]: t for t in result["selection"]["trials"] if t["model"] in {"B2", "B3"} and t["candidate"] == index}
        b2, b3 = pair["B2"]["validation"]["pr_auc"], pair["B3"]["validation"]["pr_auc"]
        lines.append(f"| {index} | {b2:.6f} | {b3:.6f} | {b3-b2:+.6f} |")
    lines += ["", "B2/B3使用相同候选、随机种子、32棵树、每节点4个候选特征及训练样本。B3新增历史输入；不能仅凭性能变化证明哪一种历史统计是改善原因。Gini重要性仅作描述，存在高基数偏好。B1采用one-hot、RF采用名义类别索引，因此B1/B2差异也包含表示方式差异。", "",
              f"测试主表的B2选中深度{selected['B2']['parameters']['maxDepth']}，B3选中深度{selected['B3']['parameters']['maxDepth']}。它比较相同搜索预算下各自选优的流程；若参数不同，测试差值不能全部归因于历史特征。同参数特征增量以预设的配对验证表为依据，没有在看到测试结果后追加配对测试。", "",
              "## 实际资源与验证", "", f"特征准备约{result['feature_audit']['prepare_seconds']:.1f}秒。正式训练固定6次，实际各候选拟合耗时如下。", "", "| 模型 | 候选 | 拟合秒数 |", "| --- | ---: | ---: |"]
    for trial in result["selection"]["trials"]:
        if trial["model"] != "B0":
            lines.append(f"| {trial['model']} | {trial['candidate']} | {trial['fit_seconds']:.2f} |")
    lines += ["", f"独立从导出的SQLite重算4组全部指标，误差不超过1e-12；核对{verified['test_rows']}行、{verified['test_positives']}个正标签和六月日期范围。数据库保留四模型逐航班分数、历史样本支持和截至4月的特征标识。", "",
              "小型结果保存在results/m3，包括完整指标、可靠性分箱、分组错误及20条确定性示例。候选模型、预处理器和六月评分Parquet保存在HDFS，逐航班索引在artifacts/predictions.sqlite。运行命令见README与m3_protocol.md。", "",
              "## 完成边界", "", "M3完成模型、指标、快照审计与评分产物；P3/P4页面、CSV/Parquet性能实验及课程材料属于后续M4/M5。历史档案回测不复原BTS当年的公开数据可用时间；风险以未取消未备降为条件，不预测取消或备降。"]
    Path("docs/milestone_m3.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print("Created docs/milestone_m3.md from verified real results")


if __name__ == "__main__":
    main()
