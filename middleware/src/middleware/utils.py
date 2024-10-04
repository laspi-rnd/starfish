# -*- coding: utf-8 -*-
from middleware.config import settings
from middleware.enums import FireFlyUrlTypeEnum, MessageType
from middleware.pydantic_models import Message
from middleware.types import JSONSerializable


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


def parse_message(raw_message: JSONSerializable) -> Message:
    """
    Parses a message from a raw message.
    """
    org = parse_org(raw_message["header"]["author"])
    data = raw_message["data"][0]["value"]
    type = MessageType(raw_message["header"]["type"])
    return Message(from_org=org, data=data, type=type)


def parse_org(author: str) -> str:
    """
    Parses an organization based on the author of the message.

    Args:
        author (str): The author of the message.

    Returns:
        str: The parsed organization.
    """
    prefix = "did:firefly:org/"
    if prefix not in author:
        raise ValueError("Author is not a valid FireFly DID")
    return author.replace(prefix, "")


def to_kebab_case(text: str) -> str:
    """
    Convert a string to kebab-case.

    Args:
        text (str): The text to convert.

    Returns:
        str: The converted text.
    """
    return text.replace(" ", "-").replace("_", "-").lower()
