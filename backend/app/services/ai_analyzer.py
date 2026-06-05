"""
AI 分析服务 — 封装 DeepSeek API 调用
优化点：
  1. 重试机制 + 超时控制
  2. 行业特化 prompt
  3. 更健壮的 JSON 解析
  4. 缓存分析结果
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional

from openai import OpenAI

from app.config import settings
from app.cache import cache

logger = logging.getLogger(__name__)

# 客户端延迟初始化
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.deepseek_api_key:
            raise ValueError("DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY")
        _client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.ai_request_timeout,
        )
    return _client


# ========== 行业特化规则 ==========

INDUSTRY_RULES = {
    "银行": """
行业特殊规则（银行/金融）：
- 不要关注"资产负债率"，银行本身是高杠杆经营（通常>90%是正常的）
- 重点关注：净息差（NIM）、不良贷款率、拨备覆盖率、资本充足率
- 收入结构关注：利息净收入 vs 手续费及佣金收入的占比变化
- 银行没有"毛利率"概念，不要提及
""",
    "医药": """
行业特殊规则（医药/生物）：
- 重点关注：研发费用率（>15%为研发驱动型）、核心产品集中度、管线进展
- 关注集采政策影响：产品是否进入集采、中标价格降幅
- 关注一致性评价进展
""",
    "食品饮料": """
行业特殊规则（食品饮料/消费）：
- 重点关注：预收账款/合同负债变化（反映渠道信心）、经销商数量变化
- 关注毛利率和销售费用率的平衡
- 季节性特征明显，同比比环比更有意义
""",
    "房地产": """
行业特殊规则（房地产）：
- 关注：预售收入确认节奏、合同负债变化、拿地强度
- 关注净负债率（而非普通的资产负债率）
- 关注三道红线指标
""",
}


def _get_industry_rules(industry: str) -> str:
    """根据行业返回特化规则"""
    if not industry:
        return ""
    for key, rules in INDUSTRY_RULES.items():
        if key in industry:
            return rules
    return ""


# ========== System Prompts ==========

SYSTEM_PROMPT_QUICK = """你是一名经验丰富的A股分析师。你的任务是基于提供的股票数据，输出一份简洁、客观的分析摘要。

== 角色 ==
- 你擅长从财务数据中发现值得关注的信息
- 你的分析风格是"客观、冷静、有数据支撑"
- 你会主动标注不确定的地方

== 输入数据 ==
你会收到以下结构化数据（JSON格式）：
- 股票基本信息（代码、名称、行业、市值等）
- 近几个季度的核心财务数据
- 近期公告标题列表

{industry_rules}

== 输出格式 ==
严格按照以下JSON格式输出，不要输出 markdown 代码块标记，只输出纯JSON：

{{
  "summary": "一句话概述这家公司当前的经营状况和值得关注的核心变化（50字以内）",
  "strengths": [
    "亮点1：必须引用具体数据。如'2025Q1营收同比增长12.3%，连续3个季度加速'",
    "亮点2",
    "亮点3"
  ],
  "risks": [
    "风险1：必须引用具体数据并说明为什么值得关注。如'应收账款增速(25%)远超营收增速(12%)，可能意味着回款恶化'",
    "风险2",
    "风险3"
  ],
  "metrics_commentary": "对核心指标变化的综合解读，2-3句话，重点放在趋势和结构性变化上"
}}

== 严格约束 ==
1. 所有财务数据必须从提供的源数据中引用原文，绝对不能编造或自行计算数字
2. 引用数字必须和源数据完全一致
3. 不能给出买卖建议、目标价或股价预测
4. 不确定的判断请标注"[需核实]"
5. 亮点和风险都要有具体数据支撑，不能是空泛评价
6. strengths 和 risks 各至少写2条、最多4条
7. 如果某方面数据不足，诚实标注"现有数据不足以判断"
8. 涉及增长率时必须标注比较基准（同比/环比/对比哪个报告期）
9. 不要输出 markdown 代码块标记"""


SYSTEM_PROMPT_REPORT = """你是一名资深的A股分析师，正在撰写一份标准的研究报告。你的写作风格客观、专业、数据驱动。

{industry_rules}

== 输出要求 ==
报告使用 Markdown 格式，包含以下章节：

## 第一章 公司概览
- 公司基本信息（代码、全称、上市日期、所属行业、当前市值）
- 主营业务概述（50字以内）

## 第二章 财务分析
- 收入与利润趋势（引用具体数据，分析增长节奏和质量）
- 盈利能力变化（关注利润率/ROE的趋势和驱动因素）
- 现金流状况（经营现金流与净利润的匹配度）
- 需要关注的财务信号（异常变动的科目）

## 第三章 风险识别
按风险等级（高/中/低）列出发现的风险信号，每条包含：
- 风险描述
- 数据证据
- 值得关注的原因

## 第四章 近期重要事件
从公告列表中提炼3-5条最值得关注的事件，每条约1-2句话

## 第五章 总结
- 公司核心优势（3-5点，客观陈述）
- 值得关注的风险（按重要性排列）
- 数据不足之处说明

---

**免责声明**：本报告由AI自动生成，数据来源为公开财务报告和公告信息。报告内容仅供参考，不构成任何投资建议。

== 核心原则 ==
1. 所有数字从提供的源数据中引用，绝对不能编造
2. 不能给出买卖建议、目标价、股价预测
3. 不能使用"建议买入""估值偏低""推荐"等措辞
4. 不确定的地方使用"从现有数据来看""需进一步核实"等客观表述
5. 涉及增长率必须标注比较基准（同比/环比）
6. 每个章节的标题使用 ## 二级标题格式
7. 直接输出报告正文，不要输出其他解释性文字"""


# ========== 核心函数 ==========

def _parse_ai_json(text: str) -> dict:
    """健壮的 JSON 解析，处理各种格式问题"""
    # 去除 markdown 代码块标记
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # 去除开头的 ```json 或 ```
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        # 去除结尾的 ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试修复常见问题：末尾多余逗号
        import re
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}\n原文: {cleaned[:500]}")
            raise


def quick_analysis(
    code: str,
    stock_info: dict,
    financials: list[dict],
    announcements: list[dict],
) -> dict:
    """快速分析（轻量，用于详情页内嵌展示）"""

    # 检查缓存
    cache_key = f"quick_analysis:{code}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.debug(f"快速分析命中缓存: {code}")
        return cached_result

    industry = stock_info.get("industry", "")
    industry_rules = _get_industry_rules(industry)

    # 构建 prompt
    prompt = SYSTEM_PROMPT_QUICK.format(industry_rules=industry_rules)

    context = {
        "股票代码": code,
        "股票名称": stock_info.get("name", ""),
        "行业": industry or "未知",
        "上市日期": str(stock_info.get("listing_date", "")),
        "财务数据（单位：亿元，比率为百分比）": [
            {k: v for k, v in f.items() if v is not None}
            for f in financials[-8:]
        ],
        "近期公告标题": [a.get("title", "") for a in announcements[:10]],
    }

    # 调用 AI（带重试）
    for attempt in range(settings.ai_max_retries):
        try:
            client = _get_client()
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False, indent=2)},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            text = resp.choices[0].message.content.strip()
            result = _parse_ai_json(text)

            # 验证结果结构
            if "summary" not in result:
                raise ValueError("AI 返回缺少 summary 字段")

            # 确保列表字段存在
            result.setdefault("strengths", [])
            result.setdefault("risks", [])
            result.setdefault("metrics_commentary", "")

            # 缓存结果
            cache.set(cache_key, result, settings.cache_ttl_analysis)
            logger.info(f"快速分析完成: {code}")
            return result

        except Exception as e:
            logger.warning(f"快速分析失败 (attempt {attempt + 1}): {code} - {e}")
            if attempt < settings.ai_max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"快速分析最终失败: {code}")
                return {
                    "summary": f"AI 分析暂时不可用，请稍后重试",
                    "strengths": ["数据已加载，AI 解读功能暂时不可用"],
                    "risks": ["请检查 API 配置或网络连接"],
                    "metrics_commentary": "可以查看下方图表了解财务趋势",
                }


def deep_analysis(
    code: str,
    stock_info: dict,
    financials: list[dict],
    announcements: list[dict],
) -> str:
    """深度分析 — 生成完整报告（Markdown）"""
    industry = stock_info.get("industry", "")
    industry_rules = _get_industry_rules(industry)
    prompt = SYSTEM_PROMPT_REPORT.format(industry_rules=industry_rules)

    context = {
        "股票基本信息": stock_info,
        "财务数据（单位：亿元，比率为百分比。最近8个报告期）": [
            {k: v for k, v in f.items() if v is not None}
            for f in financials[-8:]
        ],
        "近期公告标题列表": [a.get("title", "") for a in announcements[:15]],
    }

    for attempt in range(settings.ai_max_retries):
        try:
            client = _get_client()
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False, indent=2)},
                ],
                temperature=0.3,
                max_tokens=8000,
            )
            content = resp.choices[0].message.content.strip()
            logger.info(f"深度分析完成: {code}, 长度: {len(content)}")
            return content

        except Exception as e:
            logger.warning(f"深度分析失败 (attempt {attempt + 1}): {code} - {e}")
            if attempt < settings.ai_max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"深度分析最终失败: {code}")
                return f"""# 报告生成失败

**错误信息**：AI 服务暂时不可用

**可能原因**：
- API Key 配置错误
- 网络连接问题
- API 服务限流

请检查后端 `.env` 文件中的 `DEEPSEEK_API_KEY` 配置，然后重试。
"""


def summarize_announcement(title: str, content: str) -> str:
    """公告 AI 摘要"""
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是公告信息提炼助手。输入公告标题和内容，用1-2句话总结核心信息。\n"
                        "规则：\n"
                        "- 第一句：公告类型+核心变化\n"
                        "- 第二句（可选）：对投资者的可能影响\n"
                        "- 不超过80字\n"
                        "- 常规公告（如董事会决议通过日常议案）标注'常规公告'"
                    ),
                },
                {"role": "user", "content": f"标题：{title}\n内容：{content[:3000]}"},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"公告摘要生成失败: {e}")
        return ""
