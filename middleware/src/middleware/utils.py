# -*- coding: utf-8 -*-
from middleware.config import settings
from middleware.enums import FireFlyUrlTypeEnum


def build_firefly_url(
    path: str,
    *,
    url_type: FireFlyUrlTypeEnum = FireFlyUrlTypeEnum.REST,
) -> str:
    """
    Build a FireFly URL.

    Args:
        path (str): The path to append to the base URL.
        url_type (FireFlyUrlTypeEnum): The type of URL to build.

    Returns:
        str: The built URL.
    """
    if url_type == FireFlyUrlTypeEnum.REST:
        url = f"{settings.firefly_api_scheme}://{settings.firefly_api_host}:{settings.firefly_api_port}"
    elif url_type == FireFlyUrlTypeEnum.WS:
        url = f"ws://{settings.firefly_api_host}:{settings.firefly_api_port}"
    else:
        raise ValueError(f"Unsupported URL type: {url_type}")
    return f"{url}{path}"


def to_kebab_case(text: str) -> str:
    """
    Convert a string to kebab-case.

    Args:
        text (str): The text to convert.

    Returns:
        str: The converted text.
    """
    return text.replace(" ", "-").replace("_", "-").lower()
