#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立PDF报告生成器 - 数据分析版（性能优化版）
重点突出批次数据分析，简化AI建议
优化：降低DPI、字体缓存、异步支持
"""

import os
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import numpy as np

# ============================================
# 性能优化配置
# ============================================
CHART_DPI = 100  # 降低DPI提高生成速度（原150）
CHART_QUALITY = 85  # JPEG质量

# 字体缓存（全局变量，只加载一次）
_CACHED_FONT_NAME = None
_FONT_LOADED = False

# ============================================
# 数据结构定义
# ============================================

@dataclass
class BatchAnalysisData:
    """批次数据分析结构"""
    # 批次信息
    batch_number: int                    # 批次号
    batch_size: int                      # 本批次数据量
    total_records: int                   # 数据库总记录数
    report_period: str                   # 报告时间范围

    # 质量概览
    average_score: float                 # 平均总分
    score_distribution: Dict[str, int]   # 分数分布 (优秀/良好/合格/需改进)

    # 技能分析 (基于本批次)
    skill_analysis: Dict[str, float]     # 各技能平均分
    skill_trend: List[float]             # 总分趋势 (最近10条)

    # 缺陷分析
    defect_stats: Dict[str, int]         # 缺陷类型统计
    defect_rate: float                   # 缺陷率

    # 详细数据 (用于表格展示)
    detail_records: List[Dict] = field(default_factory=list)

    # AI建议 (简化)
    ai_summary: str = ""                 # AI总结 (一句话)
    key_recommendations: List[str] = field(default_factory=list)  # 2-3条关键建议

    generated_at: str = ""


# ============================================
# PDF模板配置
# ============================================

class PDFTheme:
    """PDF主题配置"""
    # 主色调 - 专业蓝
    PRIMARY = colors.HexColor("#2563eb")
    SECONDARY = colors.HexColor("#3b82f6")
    ACCENT = colors.HexColor("#10b981")
    WARNING = colors.HexColor("#f59e0b")
    DANGER = colors.HexColor("#ef4444")

    # 分数等级颜色
    SCORE_EXCELLENT = colors.HexColor("#10b981")  # >=90 绿色
    SCORE_GOOD = colors.HexColor("#3b82f6")       # >=80 蓝色
    SCORE_PASS = colors.HexColor("#f59e0b")       # >=70 橙色
    SCORE_FAIL = colors.HexColor("#ef4444")       # <70 红色

    TEXT_DARK = colors.HexColor("#1f2937")
    TEXT_GRAY = colors.HexColor("#6b7280")
    BG_LIGHT = colors.HexColor("#f9fafb")
    BG_TABLE_HEADER = colors.HexColor("#dbeafe")


# ============================================
# 图表生成器
# ============================================

class ChartGenerator:
    """图表生成器（优化版）"""

    _font_configured = False

    @staticmethod
    def setup_chinese_font():
        """设置matplotlib中文字体（只配置一次）"""
        if ChartGenerator._font_configured:
            return
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        ChartGenerator._font_configured = True

    @staticmethod
    def create_score_trend_chart(trend_data: List[float], output_buffer: io.BytesIO = None):
        """创建分数趋势折线图（优化DPI）"""
        ChartGenerator.setup_chinese_font()

        fig, ax = plt.subplots(figsize=(10, 3.5))  # 稍微缩小尺寸

        x = range(1, len(trend_data) + 1)
        ax.plot(x, trend_data, marker='o', linewidth=2, markersize=5, color='#2563eb')
        ax.fill_between(x, trend_data, alpha=0.3, color='#3b82f6')

        # 添加平均线
        avg = np.mean(trend_data)
        ax.axhline(y=avg, color='#10b981', linestyle='--', label=f'平均: {avg:.1f}')

        # 设置阈值线
        ax.axhline(y=80, color='#f59e0b', linestyle=':', alpha=0.7, label='良好线(80)')
        ax.axhline(y=70, color='#ef4444', linestyle=':', alpha=0.7, label='合格线(70)')

        ax.set_xlabel('检测序号', fontsize=10)
        ax.set_ylabel('总分', fontsize=10)
        ax.set_title('质量趋势分析', fontsize=12, fontweight='bold', pad=10)
        ax.set_ylim(50, 100)
        ax.legend(loc='lower right', fontsize=9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if output_buffer:
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)
        else:
            output_buffer = io.BytesIO()
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)

        plt.close()
        return output_buffer

    @staticmethod
    def create_skill_radar_chart(skill_data: Dict[str, float], output_buffer: io.BytesIO = None):
        """创建技能雷达图（优化DPI）"""
        ChartGenerator.setup_chinese_font()

        if not skill_data:
            return None

        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))  # 稍微缩小

        labels = list(skill_data.keys())
        values = list(skill_data.values())

        # 闭合雷达图
        values += values[:1]
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        angles += angles[:1]

        ax.plot(angles, values, 'o-', linewidth=2, color='#2563eb')
        ax.fill(angles, values, alpha=0.25, color='#3b82f6')

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylim(0, 100)
        ax.set_title('技能分析雷达图', fontsize=12, fontweight='bold', pad=15)

        plt.tight_layout()

        if output_buffer:
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)
        else:
            output_buffer = io.BytesIO()
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)

        plt.close()
        return output_buffer

    @staticmethod
    def create_defect_pie_chart(defect_data: Dict[str, int], output_buffer: io.BytesIO = None):
        """创建缺陷分布饼图（优化DPI）"""
        ChartGenerator.setup_chinese_font()

        if not defect_data:
            return None

        fig, ax = plt.subplots(figsize=(7, 5))  # 稍微缩小

        labels = list(defect_data.keys())
        sizes = list(defect_data.values())

        # 颜色配置
        colors_list = ['#ef4444', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#10b981']

        # 突出最大的扇区
        explode = [0.05 if i == sizes.index(max(sizes)) else 0 for i in range(len(sizes))]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.1f%%',
            colors=colors_list[:len(labels)],
            explode=explode, startangle=90,
            textprops={'fontsize': 9}
        )

        ax.set_title('缺陷类型分布', fontsize=12, fontweight='bold', pad=12)

        plt.tight_layout()

        if output_buffer:
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)
        else:
            output_buffer = io.BytesIO()
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)

        plt.close()
        return output_buffer

    @staticmethod
    def create_score_distribution_chart(distribution: Dict[str, int], output_buffer: io.BytesIO = None):
        """创建分数分布柱状图（优化DPI）"""
        ChartGenerator.setup_chinese_font()

        fig, ax = plt.subplots(figsize=(7, 4))  # 稍微缩小

        labels = ['优秀(≥90)', '良好(80-89)', '合格(70-79)', '需改进(<70)']
        values = [
            distribution.get('优秀', 0),
            distribution.get('良好', 0),
            distribution.get('合格', 0),
            distribution.get('需改进', 0)
        ]
        colors_list = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']

        bars = ax.bar(labels, values, color=colors_list, edgecolor='white', linewidth=1.5)

        # 在柱子上显示数值
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                   str(val), ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.set_ylabel('检测次数', fontsize=10)
        ax.set_title('质量等级分布', fontsize=12, fontweight='bold', pad=12)
        ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 10)

        plt.tight_layout()

        if output_buffer:
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)
        else:
            output_buffer = io.BytesIO()
            plt.savefig(output_buffer, format='png', dpi=CHART_DPI, bbox_inches='tight', optimize=True)
            output_buffer.seek(0)

        plt.close()
        return output_buffer


# ============================================
# PDF生成器
# ============================================

def get_cached_font() -> str:
    """获取缓存的中文字体（全局缓存，只加载一次）"""
    global _CACHED_FONT_NAME, _FONT_LOADED

    if _FONT_LOADED and _CACHED_FONT_NAME:
        return _CACHED_FONT_NAME

    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('Chinese', path))
                _CACHED_FONT_NAME = 'Chinese'
                _FONT_LOADED = True
                return 'Chinese'
            except:
                continue

    _CACHED_FONT_NAME = 'Helvetica'
    _FONT_LOADED = True
    return 'Helvetica'


class DataAnalysisPDFGenerator:
    """数据分析版PDF生成器（优化版）"""

    BATCH_SIZE = 30  # 批次大小

    def __init__(self):
        self.theme = PDFTheme()
        self.chinese_font = get_cached_font()  # 使用缓存的字体

    def _create_styles(self) -> Dict:
        """创建样式"""
        styles = getSampleStyleSheet()

        return {
            'title': ParagraphStyle(
                'Title', parent=styles['Title'],
                fontSize=24, textColor=self.theme.PRIMARY,
                fontName=self.chinese_font, alignment=1, spaceAfter=10
            ),
            'subtitle': ParagraphStyle(
                'Subtitle', parent=styles['Normal'],
                fontSize=12, textColor=self.theme.TEXT_GRAY,
                fontName=self.chinese_font, alignment=1, spaceAfter=20
            ),
            'heading': ParagraphStyle(
                'Heading', parent=styles['Heading1'],
                fontSize=16, textColor=self.theme.PRIMARY,
                fontName=self.chinese_font, spaceBefore=20, spaceAfter=12
            ),
            'subheading': ParagraphStyle(
                'SubHeading', parent=styles['Heading2'],
                fontSize=14, textColor=self.theme.SECONDARY,
                fontName=self.chinese_font, spaceBefore=15, spaceAfter=8
            ),
            'body': ParagraphStyle(
                'Body', parent=styles['Normal'],
                fontSize=11, textColor=self.theme.TEXT_DARK,
                fontName=self.chinese_font, spaceBefore=4, spaceAfter=4
            ),
            'highlight': ParagraphStyle(
                'Highlight', parent=styles['Normal'],
                fontSize=12, textColor=self.theme.PRIMARY,
                fontName=self.chinese_font, spaceBefore=8, spaceAfter=8
            ),
            'small': ParagraphStyle(
                'Small', parent=styles['Normal'],
                fontSize=9, textColor=self.theme.TEXT_GRAY,
                fontName=self.chinese_font
            )
        }

    def generate_pdf(self, data: BatchAnalysisData, output_path: str):
        """生成PDF报告"""
        print(f"[START] 生成PDF: {output_path}")

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = self._create_styles()
        story = []

        # ========== 封面 ==========
        story.append(Paragraph("焊缝质量检测分析报告", styles['title']))
        story.append(Paragraph(f"第 {data.batch_number} 批次 | {data.batch_size} 条数据", styles['subtitle']))
        story.append(Paragraph(f"时间范围: {data.report_period}", styles['subtitle']))
        story.append(Spacer(1, 20))

        # ========== 一、质量概览 ==========
        story.append(Paragraph("一、质量概览", styles['heading']))

        # 核心指标卡片
        overview_data = [
            ['指标', '数值', '状态'],
            ['平均分数', f'{data.average_score:.1f} 分', self._get_score_status(data.average_score)],
            ['检测总数', f'{data.total_records} 次', f'本批次 {data.batch_size} 次'],
            ['缺陷率', f'{data.defect_rate:.1f}%', '需关注' if data.defect_rate > 30 else '良好'],
        ]

        overview_table = Table(overview_data, colWidths=[5*cm, 4*cm, 4*cm])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.theme.BG_TABLE_HEADER),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.theme.PRIMARY),
            ('FONTNAME', (0, 0), (-1, -1), self.chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, self.theme.TEXT_GRAY),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 15))

        # 分数分布图
        try:
            dist_buffer = ChartGenerator.create_score_distribution_chart(data.score_distribution)
            if dist_buffer:
                story.append(Paragraph("质量等级分布", styles['subheading']))
                story.append(Image(dist_buffer, width=14*cm, height=8*cm))
        except Exception as e:
            print(f"[WARN] 分数分布图生成失败: {e}")

        story.append(Spacer(1, 15))

        # ========== 二、趋势分析 ==========
        story.append(Paragraph("二、趋势分析", styles['heading']))

        if data.skill_trend:
            try:
                trend_buffer = ChartGenerator.create_score_trend_chart(data.skill_trend)
                if trend_buffer:
                    story.append(Paragraph("总分变化趋势", styles['subheading']))
                    story.append(Image(trend_buffer, width=15*cm, height=5*cm))
                    story.append(Spacer(1, 10))
            except Exception as e:
                print(f"[WARN] 趋势图生成失败: {e}")

        # 趋势分析文字
        if data.skill_trend and len(data.skill_trend) >= 2:
            first_half = np.mean(data.skill_trend[:len(data.skill_trend)//2]) if len(data.skill_trend) >= 4 else data.skill_trend[0]
            second_half = np.mean(data.skill_trend[len(data.skill_trend)//2:]) if len(data.skill_trend) >= 4 else data.skill_trend[-1]
            trend_direction = "上升" if second_half > first_half else "下降" if second_half < first_half else "稳定"
            change = abs(second_half - first_half)

            trend_text = f"趋势分析: 整体质量呈{trend_direction}趋势，变化幅度 {change:.1f} 分"
            story.append(Paragraph(trend_text, styles['body']))

        story.append(Spacer(1, 15))

        # ========== 三、技能分析 ==========
        story.append(Paragraph("三、技能分析", styles['heading']))

        if data.skill_analysis:
            # 雷达图
            try:
                radar_buffer = ChartGenerator.create_skill_radar_chart(data.skill_analysis)
                if radar_buffer:
                    story.append(Image(radar_buffer, width=12*cm, height=12*cm))
            except Exception as e:
                print(f"[WARN] 雷达图生成失败: {e}")

            # 技能详情表格
            skill_data = [['技能项', '平均分', '等级']]
            for skill, score in data.skill_analysis.items():
                level = '优秀' if score >= 90 else '良好' if score >= 80 else '合格' if score >= 70 else '需改进'
                skill_data.append([skill, f'{score:.1f}', level])

            skill_table = Table(skill_data, colWidths=[6*cm, 4*cm, 4*cm])
            skill_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.theme.BG_TABLE_HEADER),
                ('FONTNAME', (0, 0), (-1, -1), self.chinese_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, self.theme.TEXT_GRAY),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(skill_table)

        story.append(Spacer(1, 15))

        # ========== 四、缺陷分析 ==========
        story.append(Paragraph("四、缺陷分析", styles['heading']))

        if data.defect_stats:
            # 缺陷饼图
            try:
                pie_buffer = ChartGenerator.create_defect_pie_chart(data.defect_stats)
                if pie_buffer:
                    story.append(Image(pie_buffer, width=12*cm, height=9*cm))
            except Exception as e:
                print(f"[WARN] 缺陷饼图生成失败: {e}")

            # 缺陷统计表格
            defect_data = [['缺陷类型', '出现次数', '占比']]
            total_defects = sum(data.defect_stats.values())
            for defect, count in sorted(data.defect_stats.items(), key=lambda x: x[1], reverse=True):
                ratio = f'{(count/total_defects*100):.1f}%' if total_defects > 0 else '0%'
                defect_data.append([defect, f'{count} 次', ratio])

            defect_table = Table(defect_data, colWidths=[5*cm, 4*cm, 4*cm])
            defect_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.theme.DANGER),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, -1), self.chinese_font),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, self.theme.TEXT_GRAY),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(defect_table)

        story.append(PageBreak())

        # ========== 五、详细数据 ==========
        story.append(Paragraph("五、检测数据明细", styles['heading']))

        if data.detail_records:
            # 最多显示30条
            records_to_show = data.detail_records[:30]

            detail_header = ['序号', '时间', '总分', '光滑度', '宽度', '缺陷控制', '缺陷类型']
            detail_data = [detail_header]

            for i, record in enumerate(records_to_show, 1):
                timestamp = record.get('timestamp', '')[:16] if record.get('timestamp') else '-'
                detail_data.append([
                    str(i),
                    timestamp,
                    f"{record.get('total_score', 0):.1f}",
                    f"{record.get('smoothness', 0):.1f}",
                    f"{record.get('width', 0):.1f}",
                    f"{record.get('defect', 0):.1f}",
                    record.get('defect_type', '-')[:6]
                ])

            detail_table = Table(detail_data, colWidths=[1.2*cm, 2.8*cm, 1.8*cm, 2*cm, 2*cm, 2.2*cm, 2.5*cm])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.theme.PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, -1), self.chinese_font),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, self.theme.TEXT_GRAY),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                # 根据分数着色
                *self._get_score_row_colors(detail_data)
            ]))
            story.append(detail_table)
        else:
            story.append(Paragraph("暂无详细数据", styles['body']))

        story.append(Spacer(1, 20))

        # ========== 六、总结与建议 ==========
        story.append(Paragraph("六、总结与建议", styles['heading']))

        if data.ai_summary:
            story.append(Paragraph(f"<b>AI总结:</b> {data.ai_summary}", styles['body']))
            story.append(Spacer(1, 10))

        if data.key_recommendations:
            story.append(Paragraph("<b>关键建议:</b>", styles['body']))
            for i, rec in enumerate(data.key_recommendations[:3], 1):
                story.append(Paragraph(f"  {i}. {rec}", styles['body']))
        else:
            # 基于数据自动生成建议
            auto_recs = self._generate_auto_recommendations(data)
            story.append(Paragraph("<b>改进建议:</b>", styles['body']))
            for i, rec in enumerate(auto_recs, 1):
                story.append(Paragraph(f"  {i}. {rec}", styles['body']))

        # ========== 页脚 ==========
        story.append(Spacer(1, 30))
        footer = f"<font color='gray'>焊育智眸系统 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</font>"
        story.append(Paragraph(footer, styles['small']))

        # 构建PDF
        doc.build(story)
        print(f"[OK] PDF生成完成: {output_path}")

    def _get_score_status(self, score: float) -> str:
        """获取分数状态描述"""
        if score >= 90:
            return '优秀'
        elif score >= 80:
            return '良好'
        elif score >= 70:
            return '合格'
        else:
            return '需改进'

    def _get_score_row_colors(self, table_data: List) -> List:
        """根据分数设置行颜色"""
        styles = []
        for i, row in enumerate(table_data[1:], 1):  # 跳过表头
            try:
                score = float(row[2])  # 总分在第3列
                if score >= 90:
                    styles.append(('BACKGROUND', (2, i), (2, i), colors.HexColor('#dcfce7')))
                elif score >= 80:
                    styles.append(('BACKGROUND', (2, i), (2, i), colors.HexColor('#dbeafe')))
                elif score >= 70:
                    styles.append(('BACKGROUND', (2, i), (2, i), colors.HexColor('#fef3c7')))
                else:
                    styles.append(('BACKGROUND', (2, i), (2, i), colors.HexColor('#fee2e2')))
            except:
                pass
        return styles

    def _generate_auto_recommendations(self, data: BatchAnalysisData) -> List[str]:
        """基于数据自动生成建议"""
        recs = []

        # 基于平均分
        if data.average_score < 70:
            recs.append("整体质量偏低，建议加强基础焊接技能训练")
        elif data.average_score < 80:
            recs.append("质量有提升空间，建议针对性练习薄弱环节")

        # 基于缺陷率
        if data.defect_rate > 30:
            recs.append(f"缺陷率偏高({data.defect_rate:.1f}%)，需重点关注缺陷预防")

        # 基于技能分析
        if data.skill_analysis:
            weak_skill = min(data.skill_analysis.items(), key=lambda x: x[1])
            if weak_skill[1] < 80:
                recs.append(f"「{weak_skill[0]}」技能较弱，建议专项强化")

        # 基于趋势
        if data.skill_trend and len(data.skill_trend) >= 4:
            first_half = np.mean(data.skill_trend[:len(data.skill_trend)//2])
            second_half = np.mean(data.skill_trend[len(data.skill_trend)//2:])
            if second_half < first_half:
                recs.append("近期质量有下降趋势，建议及时调整练习方法")

        if not recs:
            recs.append("继续保持当前练习强度，稳步提升焊接技能")

        return recs[:3]


# ============================================
# 数据获取函数
# ============================================

def fetch_batch_data_from_api() -> BatchAnalysisData:
    """从API获取批次数据"""
    import requests

    # generate-pdf 启 subprocess 时把 student_id 塞 env 里，让 /lesson-plan 走单人
    # filter；不带就是老的全班聚合
    student_id = os.environ.get("PDF_STUDENT_ID")
    params = {"student_id": student_id} if student_id else None

    try:
        print(">> 从API获取批次数据...")
        if student_id:
            print(f"   单人模式: student_id={student_id}")

        response = requests.get('http://127.0.0.1:8000/api/v1/lesson-plan', params=params, timeout=10)
        if response.status_code != 200:
            raise Exception(f"API返回错误: {response.status_code}")

        api_data = response.json()
        total_detections = api_data.get('total_detections', 0)
        print(f"   报告数据: {total_detections} 条记录")

        # 历史详情同样按学生过滤一下，否则单人 PDF 里会混进别人记录
        detail_records = []
        try:
            detail_response = requests.get(
                'http://127.0.0.1:8000/api/v1/dashboard/history',
                params=params,
                timeout=10,
            )
            if detail_response.status_code == 200:
                history_data = detail_response.json()
                # dashboard/history 返回的是列表，不是 {history: [...]}
                if isinstance(history_data, list):
                    detail_records = history_data
                else:
                    detail_records = history_data.get('history', [])
                print(f"   检测历史: {len(detail_records)} 条记录")
        except Exception as e:
            print(f"   获取检测历史失败: {e}")

        # 如果没有数据，返回空数据而不是模拟数据
        if total_detections == 0:
            print("   没有检测数据")
            return BatchAnalysisData(
                batch_number=1,
                batch_size=0,
                total_records=0,
                report_period="暂无数据",
                average_score=0,
                score_distribution={'优秀': 0, '良好': 0, '合格': 0, '需改进': 0},
                skill_analysis={},
                skill_trend=[],
                defect_stats={},
                defect_rate=0,
                detail_records=[],
                ai_summary="暂无检测数据，请先进行焊接检测",
                key_recommendations=["请先上传视频或图片进行焊接检测"],
                generated_at=datetime.now().isoformat()
            )

        # 计算批次信息
        total = total_detections
        batch_number = (total - 1) // 30 + 1 if total > 0 else 1
        batch_size = min(total, 30) if total > 30 else total

        # 计算分数分布（使用真实数据）
        score_dist = {'优秀': 0, '良好': 0, '合格': 0, '需改进': 0}
        if detail_records:
            for r in detail_records:
                score = r.get('total_score', r.get('score', 0))
                if score >= 90:
                    score_dist['优秀'] += 1
                elif score >= 80:
                    score_dist['良好'] += 1
                elif score >= 70:
                    score_dist['合格'] += 1
                else:
                    score_dist['需改进'] += 1

        # 计算趋势数据（使用真实数据）
        skill_trend = []
        if detail_records:
            # 取最近30条数据的总分作为趋势
            recent_records = detail_records[-30:] if len(detail_records) > 30 else detail_records
            for r in recent_records:
                score = r.get('total_score', r.get('score', 0))
                skill_trend.append(float(score))

        # 计算缺陷统计（使用真实数据）
        defect_stats = {}
        defect_count = 0
        for rec in detail_records:
            defect = rec.get('defect_type_name', rec.get('defect_type', '未知'))
            if defect and defect not in ['良好焊缝', '无缺陷', 'Good Weld', 'Good', '']:
                defect_stats[defect] = defect_stats.get(defect, 0) + 1
                defect_count += 1

        defect_rate = (defect_count / len(detail_records) * 100) if detail_records else 0

        # 构建详细记录列表（用于表格展示）
        formatted_records = []
        for r in detail_records[:30]:  # 只取最近30条
            formatted_records.append({
                'timestamp': r.get('timestamp', ''),
                'total_score': r.get('total_score', r.get('score', 0)),
                'smoothness': r.get('smoothness_score', 0),
                'width': r.get('spacing_score', r.get('width_score', 0)),
                'defect': r.get('defect_type_score', r.get('defect_score', 0)),
                'defect_type': r.get('defect_type_name', r.get('defect_type', '未知'))
            })

        return BatchAnalysisData(
            batch_number=batch_number,
            batch_size=batch_size,
            total_records=total,
            report_period=api_data.get('report_period', ''),
            average_score=api_data.get('average_score', 0),
            score_distribution=score_dist,
            skill_analysis=api_data.get('skill_analysis', {}),
            skill_trend=skill_trend,
            defect_stats=defect_stats,
            defect_rate=defect_rate,
            detail_records=formatted_records,
            ai_summary="",
            key_recommendations=api_data.get('teaching_recommendations', [])[:3],
            generated_at=datetime.now().isoformat()
        )

    except Exception as e:
        print(f"   API获取失败: {e}")
        # 返回空数据而不是模拟数据
        return BatchAnalysisData(
            batch_number=1,
            batch_size=0,
            total_records=0,
            report_period="API连接失败",
            average_score=0,
            score_distribution={'优秀': 0, '良好': 0, '合格': 0, '需改进': 0},
            skill_analysis={},
            skill_trend=[],
            defect_stats={},
            defect_rate=0,
            detail_records=[],
            ai_summary=f"API连接失败: {str(e)}",
            key_recommendations=["请检查后端服务是否正常运行"],
            generated_at=datetime.now().isoformat()
        )


# ============================================
# 主函数
# ============================================

def main():
    """主函数"""
    print("=" * 60)
    print("焊缝质量检测分析报告生成器")
    print("=" * 60)

    # 获取数据
    data = fetch_batch_data_from_api()

    print(f"   批次: 第{data.batch_number}批次")
    print(f"   数据量: {data.batch_size}条")
    print(f"   平均分: {data.average_score:.1f}")
    print(f"   缺陷率: {data.defect_rate:.1f}%")

    # 生成PDF - 文件名统一格式
    filename = f"焊接质量分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    generator = DataAnalysisPDFGenerator()
    generator.generate_pdf(data, filename)

    print("\n" + "=" * 60)
    print(f"报告生成完成: {filename}")
    print("=" * 60)


if __name__ == "__main__":
    main()
