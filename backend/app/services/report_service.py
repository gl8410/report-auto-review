import io
import os
import httpx
from datetime import datetime
from typing import Dict, List, Any
from fastapi import Response, HTTPException
from sqlmodel import Session, select
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.core.config import settings
from app.models.review import ReviewTask, ReviewResultItem, TaskStatus
from app.models.document import Document
from app.models.rule import Rule, RuleGroup

async def generate_summary_report_content(
    document_name: str,
    rule_group_name: str,
    total_rules: int,
    stats: Dict[str, int],
    results: List[Dict[str, Any]]
) -> bytes:
    """
    Generate a 2-page PDF summary report for review results.
    Uses LLM to generate the summary text, then creates PDF.
    """
    # Register Chinese font
    font_registered = False
    try:
        # Try to use system Chinese font
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # Windows Microsoft YaHei
            "C:/Windows/Fonts/simsun.ttc",  # Windows SimSun
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux
            "/System/Library/Fonts/PingFang.ttc",  # macOS
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                font_registered = True
                break
    except Exception as e:
        print(f"Font registration error: {e}")

    # Separate results by risk_level and result_code
    serious_problems = [r for r in results if r["result_code"] == "REJECT" and r.get("risk_level") == "高风险"]
    medium_problems = [r for r in results if r["result_code"] == "REJECT" and r.get("risk_level") != "高风险"]
    manual_checks = [r for r in results if r["result_code"] == "MANUAL_CHECK"]

    # Generate LLM summary
    summary_prompt = f"""你是一个工程报告审查专家。请根据以下审查结果生成一份简洁的审查摘要（200字以内）：

**审查文档**: {document_name}
**规则组**: {rule_group_name}
**总规则数**: {total_rules}
**通过**: {stats['PASS']}条
**不通过**: {stats['REJECT']}条
**待人工复核**: {stats['MANUAL_CHECK']}条

**主要问题**:
{chr(10).join([f"- 条款{r['clause_number']}: {r['reasoning'][:100]}..." for r in serious_problems[:5]]) if serious_problems else "无严重问题"}

请生成一段专业的审查总结，包括：总体评价、主要发现、建议。直接输出摘要文字，不要有任何前缀。"""

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                settings.LLM_URL,
                headers={"Authorization": f"Bearer {settings.API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            llm_summary = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM summary generation error: {e}")
        llm_summary = f"审查完成。共审查{total_rules}条规则，通过{stats['PASS']}条，不通过{stats['REJECT']}条，待人工复核{stats['MANUAL_CHECK']}条。"

    # Create PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    # Styles
    styles = getSampleStyleSheet()
    try:
        title_style = ParagraphStyle(
            'ChineseTitle',
            parent=styles['Heading1'],
            fontName='ChineseFont',
            fontSize=18,
            spaceAfter=12,
            alignment=1  # Center
        )
        heading_style = ParagraphStyle(
            'ChineseHeading',
            parent=styles['Heading2'],
            fontName='ChineseFont',
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'ChineseBody',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=10,
            leading=14,
            spaceAfter=6
        )
        small_style = ParagraphStyle(
            'ChineseSmall',
            parent=styles['Normal'],
            fontName='ChineseFont',
            fontSize=9,
            leading=12
        )
    except:
        # Fallback to default styles
        title_style = styles['Heading1']
        heading_style = styles['Heading2']
        body_style = styles['Normal']
        small_style = styles['Normal']

    story = []

    # Title
    story.append(Paragraph("文档审查报告摘要", title_style))
    story.append(Spacer(1, 10*mm))

    # Document info
    story.append(Paragraph(f"<b>审查文档：</b>{document_name}", body_style))
    story.append(Paragraph(f"<b>规则组：</b>{rule_group_name}", body_style))
    story.append(Paragraph(f"<b>生成时间：</b>{datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    story.append(Spacer(1, 5*mm))

    # Stats table - use Paragraph for Chinese text in cells
    font_name = 'ChineseFont' if font_registered else 'Helvetica'
    stats_data = [
        [Paragraph("总规则数", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1)),
         Paragraph("通过", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1)),
         Paragraph("不通过", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1)),
         Paragraph("待人工复核", ParagraphStyle('TableHeader', fontName=font_name, fontSize=10, textColor=colors.white, alignment=1))],
        [str(total_rules), str(stats['PASS']), str(stats['REJECT']), str(stats['MANUAL_CHECK'])]
    ]
    stats_table = Table(stats_data, colWidths=[40*mm, 35*mm, 35*mm, 45*mm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F3F4F6')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 8*mm))

    # Summary
    story.append(Paragraph("审查总结", heading_style))
    story.append(Paragraph(llm_summary, body_style))
    story.append(Spacer(1, 5*mm))

    # Serious problems (risk_level=高风险)
    if serious_problems:
        story.append(Paragraph("严重问题（高风险条款不通过）", heading_style))
        for i, r in enumerate(serious_problems[:8], 1):  # Limit to 8
            clause = r.get('clause_number', 'N/A')
            reason = (r.get('reasoning') or '')[:150]
            suggestion = (r.get('suggestion') or '')[:100]
            story.append(Paragraph(f"<b>{i}. 条款 {clause}</b>", small_style))
            story.append(Paragraph(f"问题：{reason}...", small_style))
            if suggestion:
                story.append(Paragraph(f"建议：{suggestion}...", small_style))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))

    # Other problems
    if medium_problems:
        story.append(Paragraph("其他问题（中/低风险条款不通过）", heading_style))
        for i, r in enumerate(medium_problems[:6], 1):  # Limit to 6
            clause = r.get('clause_number', 'N/A')
            reason = (r.get('reasoning') or '')[:100]
            story.append(Paragraph(f"{i}. 条款 {clause}：{reason}...", small_style))
        story.append(Spacer(1, 3*mm))

    # Manual check items (brief list)
    if manual_checks:
        story.append(Paragraph("待人工复核项", heading_style))
        manual_list = "、".join([r.get('clause_number', 'N/A') for r in manual_checks[:15]])
        story.append(Paragraph(f"以下条款需人工复核：{manual_list}{'...' if len(manual_checks) > 15 else ''}", small_style))

    # Build PDF
    doc.build(story)

    pdf_buffer.seek(0)
    return pdf_buffer.read()

class ReportService:
    @staticmethod
    async def generate_summary_pdf(session: Session, task_id: str) -> Response:
        """Generate a summary PDF report for a review task (max 2 pages)."""
        task = session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status != TaskStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Task is not completed yet")

        # Get document and rule group info
        doc = session.get(Document, task.document_id)
        group = session.get(RuleGroup, task.rule_group_id)

        # Get all results with rule info
        results = session.exec(
            select(ReviewResultItem).where(ReviewResultItem.task_id == task_id)
        ).all()

        enriched_results = []
        for result in results:
            rule = session.get(Rule, result.rule_id)
            enriched_results.append({
                "clause_number": rule.clause_number if rule else "N/A",
                "rule_content": rule.content if rule else "N/A",
                "risk_level": rule.risk_level if rule else "中风险",
                "result_code": result.result_code,
                "reasoning": result.reasoning,
                "evidence": result.evidence,
                "suggestion": result.suggestion
            })

        # Calculate stats
        stats = {"PASS": 0, "REJECT": 0, "MANUAL_CHECK": 0}
        for r in results:
            if r.result_code in stats:
                stats[r.result_code] += 1

        # Generate PDF using LLM for summary
        pdf_bytes = await generate_summary_report_content(
            document_name=doc.filename if doc else "Unknown",
            rule_group_name=group.name if group else "Unknown",
            total_rules=len(results),
            stats=stats,
            results=enriched_results
        )

        # Return as downloadable PDF
        safe_filename = f"review_summary_{task_id[:8]}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"'
            }
        )