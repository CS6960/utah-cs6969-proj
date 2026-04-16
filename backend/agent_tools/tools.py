import logging
import math

from langchain_core.tools import tool

from agent_tools.financial_reports_tools import (
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
)

logger = logging.getLogger(__name__)

ALLOWED_CALCULATOR_GLOBALS = {
    "__builtins__": {},
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sum": sum,
    "math": math,
}


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a math expression for arithmetic, percentages, ratios,
    and portfolio calculations.
    """
    try:
        logger.info("calculator called. expression=%s", expression)
        result = eval(expression, ALLOWED_CALCULATOR_GLOBALS, {})  # noqa: S307
        return str(result)
    except Exception as e:
        logger.exception("calculator failed. expression=%s error=%s", expression, e)
        return f"Error evaluating expression: {e!s}"


REPORT_RETRIEVAL_TOOLS = [
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
    calculator,
]
