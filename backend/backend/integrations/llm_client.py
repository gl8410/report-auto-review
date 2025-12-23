import json
import re
import httpx
from typing import List, Dict, Any, Optional
from backend.core.config import settings
from backend.schemas.rule import ParsedRulesResponse, ParsedRule

# Valid values for rule fields (moved from services.py)
VALID_REVIEW_TYPES = ["内容完整性", "计算结果准确性", "禁止条款", "前后逻辑一致性", "措施遵从性", "计算正确性"]
VALID_RISK_LEVELS = ["低风险", "中风险", "高风险"]

async def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 4096
) -> Optional[str]:
    """
    Call DeepSeek V3.1 LLM API
    """
    if not settings.API_KEY:
        raise ValueError("API_KEY not found in environment variables")
    
    headers = {
        "Authorization": f"Bearer {settings.API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    # Use longer timeout for LLM calls
    timeout_config = httpx.Timeout(300.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        try:
            response = await client.post(settings.LLM_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except httpx.ReadTimeout:
            raise Exception("LLM service timeout, please try again later")
        except httpx.ConnectTimeout:
            raise Exception("Cannot connect to LLM service")
        except httpx.HTTPStatusError as e:
            raise Exception(f"LLM service returned error: {e.response.status_code}")

async def health_check_llm() -> bool:
    """Check if LLM service is available"""
    try:
        response = await call_llm(
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        return response is not None
    except Exception:
        return False

async def parse_rules_from_text(text: str, filename: str = "") -> ParsedRulesResponse:
    """
    Parse rules from text using LLM
    """
    system_prompt = """你是一个专业的法规条文解析助手。你的任务是将上传的法规/标准文本拆解为原子化的审查规则。

请严格按照以下JSON格式输出：
{
    "standard_name": "标准/导则的完整名称",
    "rules": [
        {
            "clause_number": "条文号，如 3.1.2 或 第三条",
            "content": "该条规则的具体内容，保持原文",
            "review_type": "审查类型，必须从以下六种中选择一种：内容完整性/计算结果准确性/禁止条款/前后逻辑一致性/措施遵从性/计算正确性",
            "risk_level": "风险等级，必须从以下三种中选择一种：低风险/中风险/高风险"
        }
    ]
}

【审查类型判断标准】
- 内容完整性：要求报告必须包含某些章节、内容或信息
- 计算结果准确性：涉及数值计算结果的校核
- 禁止条款：明确禁止某些做法的强制性条款（如"不得"、"严禁"等）
- 前后逻辑一致性：要求文档内部数据、结论等前后一致
- 措施遵从性：要求采取特定的工程措施或方法
- 计算正确性：涉及计算方法、公式的正确使用

【风险等级判断标准】
- 高风险：强制性条款、涉及安全的条款、使用"必须"、"严禁"、"不得"等词
- 中风险：一般性要求、使用"应"、"应当"等词
- 低风险：建议性条款、使用"宜"、"可"等词

【重要提醒】
1. review_type 必须是上述6种之一，不能自创
2. risk_level 必须是：低风险、中风险、高风险 之一
3. clause_number 保持原文格式
4. 只输出JSON，不要其他解释文字"""

    user_prompt = f"""请解析以下法规/标准文本，将其拆解为原子化规则：

文件名：{filename}

文本内容：
{text[:15000]}"""  # Limit text length

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = await call_llm(messages, temperature=0.2, max_tokens=8000)

        if not response:
            raise ValueError("LLM returned empty response")

        # Extract JSON from response
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        # Parse JSON
        data = json.loads(json_str)

        # Validate and normalize
        parsed_response = ParsedRulesResponse(**data)

        validated_rules = []
        for rule in parsed_response.rules:
            # Normalize review_type
            if rule.review_type not in VALID_REVIEW_TYPES:
                rule.review_type = "内容完整性"
            # Normalize risk_level
            if rule.risk_level not in VALID_RISK_LEVELS:
                risk_map = {
                    "High": "高风险", "Medium": "中风险", "Low": "低风险",
                    "重要": "高风险", "中等": "中风险", "一般": "低风险"
                }
                rule.risk_level = risk_map.get(rule.risk_level, "中风险")
            validated_rules.append(rule)

        parsed_response.rules = validated_rules
        return parsed_response

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        # Try to repair truncated JSON (simplified recovery logic)
        try:
            rule_pattern = r'\{\s*"clause_number"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*"([^"]+)"\s*,\s*"review_type"\s*:\s*"([^"]+)"\s*,\s*"risk_level"\s*:\s*"([^"]+)"\s*\}'
            matches = re.findall(rule_pattern, response or "")
            if matches:
                rules = []
                for match in matches:
                    rule = ParsedRule(
                        clause_number=match[0],
                        content=match[1],
                        review_type=match[2] if match[2] in VALID_REVIEW_TYPES else "内容完整性",
                        risk_level=match[3] if match[3] in VALID_RISK_LEVELS else "中风险"
                    )
                    rules.append(rule)
                standard_match = re.search(r'"standard_name"\s*:\s*"([^"]+)"', response or "")
                standard_name = standard_match.group(1) if standard_match else filename
                return ParsedRulesResponse(standard_name=standard_name, rules=rules)
        except Exception:
            pass
        raise ValueError(f"Failed to parse LLM response: {e}")
    except Exception as e:
        print(f"LLM call error: {e}")
        raise

async def generate_review_queries(rule_content: str, review_type: str = "") -> List[str]:
    """
    Generate multiple optimized search queries from rule content
    """
    prompt = f"""你是一个文档检索专家。给定以下审查规则，请生成2-3个搜索查询词，用于在工程报告中检索相关的实际内容（不是目录标题）。

规则内容：{rule_content[:800]}
审查类型：{review_type}

要求：
1. 提取规则中的关键技术概念和数据类型
2. 生成的查询应该能匹配到文档中的具体分析内容、计算过程、数据表格
3. 避免只匹配到目录或章节标题
4. 每个查询词控制在50字以内

请直接返回JSON数组格式，例如：
["水文分析计算结果 洪峰流量", "壅水高度计算 水位变化", "冲刷深度分析数据"]"""

    try:
        messages = [
            {"role": "system", "content": "你是一个专业的文档检索助手，帮助生成精确的搜索查询。"},
            {"role": "user", "content": prompt}
        ]

        response = await call_llm(messages, temperature=0.3, max_tokens=500)

        if response:
            json_match = re.search(r'\[[\s\S]*?\]', response)
            if json_match:
                queries = json.loads(json_match.group())
                if isinstance(queries, list) and len(queries) > 0:
                    queries.append(rule_content[:300])
                    return queries[:4]
    except Exception as e:
        print(f"Error generating search queries: {e}")

    return [rule_content[:300]]

async def compare_rule_with_context(
    rule: Dict[str, Any],
    context_chunks: List[Dict],
    document_filename: str
) -> Dict[str, Any]:
    """
    Use LLM to compare a rule against retrieved document context
    """
    if not settings.API_KEY:
        raise ValueError("API_KEY not found")

    context_text = "\n\n---\n\n".join([
        f"[片段 {i+1}]\n{chunk['text']}"
        for i, chunk in enumerate(context_chunks)
    ])

    if not context_text.strip():
        context_text = "（未找到相关内容）"

    prompt = f"""你是一名专业的工程报告审查专家。请根据以下规则条款，审查文档中的相关内容是否符合要求。

## 规则信息
- 条文号: {rule.get('clause_number', 'N/A')}
- 规则内容: {rule.get('content', '')}
- 审查类型: {rule.get('review_type', '未指定')}
- 风险等级: {rule.get('risk_level', '中风险')}

## 文档名称
{document_filename}

## 文档相关内容
{context_text}

## 审查要求
请仔细分析文档内容是否符合上述规则要求，并给出审查结论。

请严格按照以下JSON格式输出（不要添加任何其他内容）：
{{
    "result_code": "PASS/REJECT/MANUAL_CHECK",
    "reasoning": "详细的判断理由，说明为什么得出该结论",
    "evidence": "引用文档中的相关原文作为证据（如有）",
    "suggestion": "如果不符合要求，给出具体的修改建议；如符合则填写'无'"
}}

注意：
- PASS: 文档内容完全符合规则要求
- REJECT: 文档内容明确不符合规则要求
- MANUAL_CHECK: 无法确定是否符合，需要人工复核（如找不到相关内容、信息不足等）
"""

    headers = {
        "Authorization": f"Bearer {settings.API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }

    timeout_config = httpx.Timeout(120.0, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout_config) as client:
        try:
            response = await client.post(settings.LLM_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                valid_codes = ["PASS", "REJECT", "MANUAL_CHECK"]
                if parsed.get("result_code") not in valid_codes:
                    parsed["result_code"] = "MANUAL_CHECK"
                return {
                    "result_code": parsed.get("result_code", "MANUAL_CHECK"),
                    "reasoning": parsed.get("reasoning", "无法解析审查结果"),
                    "evidence": parsed.get("evidence", ""),
                    "suggestion": parsed.get("suggestion", "")
                }
            else:
                return {
                    "result_code": "MANUAL_CHECK",
                    "reasoning": f"LLM响应格式异常: {content[:200]}",
                    "evidence": "",
                    "suggestion": "请人工审查"
                }
        except Exception as e:
            print(f"Review comparison error: {e}")
            return {
                "result_code": "MANUAL_CHECK",
                "reasoning": f"审查过程出错: {str(e)}",
                "evidence": "",
                "suggestion": "请人工审查"
            }

async def compare_documents_and_extract_opinions(
    draft_texts: List[str],
    approved_texts: List[str],
    draft_filenames: List[str],
    approved_filenames: List[str]
) -> List[Dict[str, Any]]:
    """
    Compare draft and approved documents to infer expert review opinions.
    """
    draft_full_text = ""
    for name, text in zip(draft_filenames, draft_texts):
        draft_full_text += f"\n\n--- Draft File: {name} ---\n{text[:50000]}"
        
    approved_full_text = ""
    for name, text in zip(approved_filenames, approved_texts):
        approved_full_text += f"\n\n--- Approved File: {name} ---\n{text[:50000]}"
        
    prompt = f"""你是一位资深的工程报告审查专家。你的任务是对比"原始稿件"和"修改后稿件"，推断出导致这些修改的"专家审查意见"。

请分析两个版本之间的差异，并推断出导致这些修改的具体专家意见。

**原始稿件（修改前）:**
{draft_full_text[:100000]} 

**修改后稿件（修改后）:**
{approved_full_text[:100000]}

**指示:**
1. 识别修改后稿件相对于原始稿件的重要变化（新增、删除、修改）。
2. 推断审查专家会给出什么样的*指示*或*意见*来导致这个变化。
3. 忽略轻微的格式或拼写错误修正。重点关注技术内容、计算、安全措施和合规要求。
4. 对于每条意见，根据其重要性提供"风险等级"（高风险/中风险/低风险）（安全性/强制性 = 高风险）。

**输出格式:**
请输出一个JSON数组，每个对象包含：
- "opinion": 推断的专家意见（例如："请补充...的计算依据"）**必须使用中文**
- "evidence": 变化的证据，格式为：
  【修改前】原始稿件中的相关文本片段
  【修改后】修改后稿件中的相关文本片段
  **必须使用中文，并包含具体的文本引用**
- "clause": 相关的章节/条款编号（如"4.2.1"），如无法识别则为null
- "risk_level": "高风险"、"中风险"或"低风险"

只返回JSON数组，不要有其他文字。
"""

    messages = [
        {"role": "system", "content": "你是一个专业的文档对比和审查意见逆向工程助手。请始终使用中文回复。"},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = await call_llm(messages, temperature=0.2, max_tokens=4000)
        
        if not response:
            return []
            
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            json_str = json_match.group(0)
            opinions = json.loads(json_str)
            return opinions
        else:
            print(f"Failed to parse JSON from LLM response: {response[:200]}")
            return []
            
    except Exception as e:
        print(f"Error in comparison: {e}")
        return []