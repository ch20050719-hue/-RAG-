"""
阶段四：学术可视化图表与 LaTeX 三线表生成脚本
Academic Charts & LaTeX Table Generator for Graduation Thesis

读取 results/baseline_comparison.csv 与 results/ablation_study.csv，
生成高质量学术论文图表 (300 DPI):
  1. baseline_comparison_bar.png - 四大基线多维度性能对比柱状图
  2. ablation_radar_chart.png   - 核心组件消融雷达图
  3. hallucination_trap_chart.png - 抗幻觉与边界诱导防守专项对比图
  4. latex_tables.txt           - 直接可用于毕业论文的 LaTeX 三线表源码
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 设置学术论文绘图风格与中文支持
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 11

RESULTS_DIR = Path(__file__).resolve().parent / "results"
BASELINE_CSV = RESULTS_DIR / "baseline_comparison.csv"
ABLATION_CSV = RESULTS_DIR / "ablation_study.csv"


def plot_baseline_bars(df: pd.DataFrame):
    """生成四大基线对比柱状图"""
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    metrics = ["Accuracy (%)", "Faithfulness (%)", "OOD Trap Defense (%)", "Cross-Domain Coverage (%)", "Overall Score"]
    metric_labels = ["准确率 (Acc)", "忠实度 (Faith)", "防诱导拒答率 (OOD)", "跨领域覆盖度 (Cross)", "综合得分 (Score)"]

    x = np.arange(len(metrics))
    width = 0.18

    colors = ['#A0AEC0', '#4299E1', '#ED8936', '#38A169']  # 渐进色阶：灰 -> 蓝 -> 橙 -> 绿
    models = df["Model"].tolist()

    for i, model_name in enumerate(models):
        row = df[df["Model"] == model_name].iloc[0]
        vals = [row[m] for m in metrics]
        offset = (i - 1.5) * width
        rects = ax.bar(x + offset, vals, width, label=model_name, color=colors[i], edgecolor='black', linewidth=0.8)

        # 在柱子上标注具体数值
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, rotation=0)

    ax.set_ylabel('得分 / 百分比 (%)', fontsize=12, fontweight='bold')
    ax.set_title('图 4-1 各基线模型在企业知识问答多维指标评测对比 (Baseline Comparison)', fontsize=14, pad=15, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=11, fontweight='bold')
    ax.set_ylim(0, 115)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9, loc='upper left', fontsize=10)

    plt.tight_layout()
    save_path = RESULTS_DIR / "baseline_comparison_bar.png"
    plt.savefig(save_path)
    plt.close()
    print(f"[PLOT] 基线对比柱状图已保存: {save_path}")


def plot_ablation_radar(df: pd.DataFrame):
    """生成消融实验雷达图"""
    categories = ["准确率", "忠实度", "边界防守", "跨领域覆盖", "综合效能"]
    metric_keys = ["Accuracy (%)", "Faithfulness (%)", "OOD Trap Defense (%)", "Cross-Domain Coverage (%)", "Overall Score"]
    num_vars = len(categories)

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True), dpi=300)

    colors = ['#38A169', '#ED8936', '#4299E1', '#A0AEC0']
    line_styles = ['-', '--', '-.', ':']

    for i, (_, row) in enumerate(df.iterrows()):
        values = [row[m] for m in metric_keys]
        values += values[:1]
        model_name = row["Model"]

        ax.plot(angles, values, color=colors[i], linewidth=2.2, linestyle=line_styles[i], label=model_name)
        ax.fill(angles, values, color=colors[i], alpha=0.15)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 100)

    plt.title('图 4-2 系统核心组件消融能力雷达图 (Ablation Radar Chart)', size=14, pad=20, fontweight='bold')
    plt.legend(loc='upper right', bbox_to_anchor=(1.25, 1.1), fontsize=10)

    plt.tight_layout()
    save_path = RESULTS_DIR / "ablation_radar_chart.png"
    plt.savefig(save_path)
    plt.close()
    print(f"[PLOT] 消融雷达图已保存: {save_path}")


def plot_hallucination_trap_defense(df: pd.DataFrame):
    """专项对比：幻觉发生率与边界外诱导防守能力"""
    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=300)

    models = ["M1 (Zero-Shot)", "M2 (Vanilla RAG)", "M3 (w/o Critic)", "M4 (Ours Full)"]
    hallu_rates = df["Hallucination Rate (%)"].tolist()
    trap_defenses = df["OOD Trap Defense (%)"].tolist()

    x = np.arange(len(models))
    width = 0.35

    rects1 = ax1.bar(x - width/2, hallu_rates, width, label='幻觉发生率 (Hallucination Rate %)', color='#E53E3E', alpha=0.85, edgecolor='black')
    rects2 = ax1.bar(x + width/2, trap_defenses, width, label='边界防守正确率 (OOD Defense %)', color='#3182CE', alpha=0.85, edgecolor='black')

    for rect in rects1:
        height = rect.get_height()
        ax1.annotate(f'{height:.1f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

    for rect in rects2:
        height = rect.get_height()
        ax1.annotate(f'{height:.1f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax1.set_ylabel('百分比 (%)', fontsize=12, fontweight='bold')
    ax1.set_title('图 4-3 各模型在知识库边界陷阱与抗幻觉能力评测对比', fontsize=14, pad=15, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, fontsize=11, fontweight='bold')
    ax1.set_ylim(0, 115)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    ax1.legend(loc='upper right', frameon=True, facecolor='white', fontsize=10)

    plt.tight_layout()
    save_path = RESULTS_DIR / "hallucination_trap_chart.png"
    plt.savefig(save_path)
    plt.close()
    print(f"[PLOT] 抗幻觉对比图已保存: {save_path}")


def generate_latex_tables(df_base: pd.DataFrame, df_ablation: pd.DataFrame):
    """生成毕业论文标准 LaTeX 三线表代码"""
    latex_text = "% =========================================================\n"
    latex_text += "% 毕业论文对比实验表 (LaTeX 三线表 Booktabs 格式)\n"
    latex_text += "% =========================================================\n\n"

    latex_text += "\\begin{table}[htbp]\n"
    latex_text += "\\centering\n"
    latex_text += "\\caption{不同架构基线在企业新人知识问答评测集上的综合性能对比}\n"
    latex_text += "\\label{tab:baseline_comparison}\n"
    latex_text += "\\begin{tabular}{lcccccc}\n"
    latex_text += "\\toprule\n"
    latex_text += "模型架构 & 准确率 (\\%) & 忠实度 (\\%) & 幻觉率 (\\%) & 防诱导率 (\\%) & 跨领域覆盖 (\\%) & 综合得分 \\\\\n"
    latex_text += "\\midrule\n"

    for _, row in df_base.iterrows():
        m_name = row["Model"].replace("&", "\\&")
        latex_text += f"{m_name} & {row['Accuracy (%)']:.1f} & {row['Faithfulness (%)']:.1f} & {row['Hallucination Rate (%)']:.1f} & {row['OOD Trap Defense (%)']:.1f} & {row['Cross-Domain Coverage (%)']:.1f} & \\textbf{{{row['Overall Score']:.1f}}} \\\\\n"

    latex_text += "\\bottomrule\n"
    latex_text += "\\end{tabular}\n"
    latex_text += "\\end{table}\n\n"

    latex_text += "% =========================================================\n"
    latex_text += "% 毕业论文消融实验表 (Ablation Study Table)\n"
    latex_text += "% =========================================================\n\n"

    latex_text += "\\begin{table}[htbp]\n"
    latex_text += "\\centering\n"
    latex_text += "\\caption{系统核心模块消融实验结果对比}\n"
    latex_text += "\\label{tab:ablation_study}\n"
    latex_text += "\\begin{tabular}{lccccc}\n"
    latex_text += "\\toprule\n"
    latex_text += "实验配置 & 准确率 (\\%) & 忠实度 (\\%) & 边界防守 (\\%) & 综合得分 & 相对增益 (\\Delta) \\\\\n"
    latex_text += "\\midrule\n"

    for _, row in df_ablation.iterrows():
        c_name = row["Configuration"].replace("&", "\\&")
        latex_text += f"{c_name} & {row['Accuracy (%)']:.1f} & {row['Faithfulness (%)']:.1f} & {row['OOD Defense (%)']:.1f} & {row['Overall Score']:.1f} & {row['Delta Score']} \\\\\n"

    latex_text += "\\bottomrule\n"
    latex_text += "\\end{tabular}\n"
    latex_text += "\\end{table}\n"

    save_path = RESULTS_DIR / "latex_tables.txt"
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(latex_text)
    print(f"[LATEX] LaTeX 三线表已输出至: {save_path}")


def main():
    if not BASELINE_CSV.exists() or not ABLATION_CSV.exists():
        print(f"[ERROR] 找不到结果数据文件，请先运行 run_baseline_experiment.py")
        sys.exit(1)

    df_base = pd.read_csv(BASELINE_CSV)
    df_ablation = pd.read_csv(ABLATION_CSV)

    plot_baseline_bars(df_base)
    plot_ablation_radar(df_base)
    plot_hallucination_trap_defense(df_base)
    generate_latex_tables(df_base, df_ablation)
    print("\n[SUCCESS] 阶段四所有学术图表与论文代码生成完毕！")


if __name__ == "__main__":
    main()
