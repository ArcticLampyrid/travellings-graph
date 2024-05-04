from dataclasses import dataclass
import json
from typing import Optional
import requests


@dataclass
class MemberRecord:
    id: int
    name: str
    status: str
    url: str
    tag: tuple[str]
    failed_reason: Optional[str] = None


def download_members():
    response = requests.get(
        "https://api.travellings.cn/all",
        timeout=30,
        headers={
            "User-Agent": " ".join(
                [
                    "Mozilla/5.0 (Linux x86_64)",
                    "AppleWebKit/537.36 (KHTML, like Gecko)",
                    "Chrome/124.0.0.0",
                    "Safari/537.36",
                    "TravellingsGraph/0.1 (Travellings.cn)",
                ]
            )
        },
    )
    response.raise_for_status()
    with open("members.json", "w", encoding="utf-8") as file:
        file.write(response.text)


def read_members():
    with open("members.json", "r", encoding="utf-8") as file:
        result = json.load(file)
    members = [
        MemberRecord(
            id=member["id"],
            name=member["name"].strip(),
            status=member["status"].strip(),
            url=member["url"].strip().replace(":///", "://"),
            tag=tuple(member["tag"].strip().split(",")) if member["tag"] else (),
            failed_reason=member["failedReason"],
        )
        for member in result["data"]
    ]
    return members
