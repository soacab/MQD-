from __future__ import annotations

import re
import zlib
from typing import Protocol

from app.core.exceptions import BusinessError


class VDriveAdapter(Protocol):
    def validate_folder_link(self, url: str) -> dict:
        ...


class MockVDriveAdapter:
    def validate_folder_link(self, url: str) -> dict:
        match = re.search(r"(?:enterprise_|folderGuid=|id=)([A-Za-z0-9_-]+)", url or "")
        if not match:
            raise BusinessError("INVALID_VDRIVE_URL", "无法从链接中解析 VDrive folderGuid")
        guid = match.group(1)
        folder_id = zlib.crc32(guid.encode("utf-8")) % 1_000_000_000
        return {
            "valid": True,
            "folder_guid": guid,
            "folder_id": folder_id,
            "folder_name": f"VDrive-{guid}",
            "folder_path": f"/mock/{guid}",
        }


def validate_vdrive_folder_link(url: str, adapter: VDriveAdapter | None = None) -> dict:
    return (adapter or MockVDriveAdapter()).validate_folder_link(url)
