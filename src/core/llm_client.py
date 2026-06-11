# src/core/llm_client.py
"""LLM 客户端 - 统一调用接口，带缓存（支持同步和异步）"""
import sys
import os
import asyncio
import logging
import concurrent.futures

# 将项目根目录添加到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from src.config.settings import (
    LLM_MODEL, LLM_API_KEY, LLM_BASE_URL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    LLM_TIMEOUT,
)
from src.utils.llm_cache import get_cached_response, set_cached_response

logger = logging.getLogger("main")
_llm = None
_async_llm = None


def get_llm():
    """获取 LLM 实例（单例）"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT
        )
    return _llm


def get_async_llm():
    """获取异步 LLM 实例（单例）"""
    global _async_llm
    if _async_llm is None:
        _async_llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT
        )
    return _async_llm


# ====================== 同步调用 ======================

def call_llm(prompt: str):
    """
    调用 LLM 并返回响应对象。
    使用线程池超时保护，避免某个请求永久挂起。
    注意：重试由上层 safe_call 处理，这里不做重试以避免双重。
    """
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(get_llm().invoke, [HumanMessage(content=prompt)])
    try:
        return future.result(timeout=LLM_TIMEOUT)
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False)  # 放弃僵尸线程，不阻塞主进程
        logger.warning(f"LLM 调用超时（{LLM_TIMEOUT}秒），将触发重试")
        raise TimeoutError(f"LLM 调用超时（{LLM_TIMEOUT}秒）")
    finally:
        executor.shutdown(wait=False)


def call_llm_with_prompt(prompt: str, use_cache: bool = True) -> str:
    """
    调用 LLM 并返回文本内容（带缓存）

    参数:
        prompt: 提示词
        use_cache: 是否使用缓存，默认 True

    返回:
        LLM 响应内容
    """
    temperature = get_llm().temperature

    # 1. 尝试从缓存获取
    if use_cache:
        cached_response = get_cached_response(prompt, temperature)
        if cached_response:
            logger.debug(f"缓存命中，长度: {len(cached_response)} 字符")
            return cached_response

    # 2. 调用 LLM
    logger.debug(f"调用 LLM，提示词长度: {len(prompt)}")

    response = call_llm(prompt)
    content = response.content

    # 3. 保存到缓存
    if use_cache:
        set_cached_response(prompt, content, temperature)

    logger.debug(f"LLM 响应长度: {len(content)} 字符")

    return content


# ====================== 异步调用 ======================

async def async_call_llm(prompt: str):
    """
    异步调用 LLM 并返回响应对象。
    使用 asyncio.wait_for 超时保护。
    注意：重试由上层 safe_call 处理，这里不做重试。
    """
    try:
        return await asyncio.wait_for(
            get_async_llm().ainvoke([HumanMessage(content=prompt)]),
            timeout=LLM_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"异步 LLM 调用超时（{LLM_TIMEOUT}秒）")


async def async_call_llm_with_prompt(prompt: str, use_cache: bool = True) -> str:
    """
    异步调用 LLM 并返回文本内容（带缓存）

    参数:
        prompt: 提示词
        use_cache: 是否使用缓存，默认 True

    返回:
        LLM 响应内容
    """
    temperature = get_async_llm().temperature

    # 1. 尝试从缓存获取
    if use_cache:
        cached_response = get_cached_response(prompt, temperature)
        if cached_response:
            logger.debug(f"缓存命中（异步），长度: {len(cached_response)} 字符")
            return cached_response

    # 2. 调用 LLM
    logger.debug(f"异步调用 LLM，提示词长度: {len(prompt)}")

    response = await async_call_llm(prompt)
    content = response.content

    # 3. 保存到缓存
    if use_cache:
        set_cached_response(prompt, content, temperature)

    logger.debug(f"异步 LLM 响应长度: {len(content)} 字符")

    return content


def debug_log(msg: str, data=None):
    """调试日志"""
    if data:
        logger.debug(f"{msg} {data}")
    else:
        logger.debug(msg)