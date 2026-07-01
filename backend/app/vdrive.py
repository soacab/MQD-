from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import zlib
from typing import Any, Protocol

from app.core.config import settings
from app.core.exceptions import BusinessError


class VDriveAdapter(Protocol):
    def validate_folder_link(self, url: str) -> dict:
        ...

    def list_folder_children(self, folder_id: int, page_num: int, page_size: int = 100) -> dict:
        ...

    def list_files(self, folder_id: int, root_path: str | None = None) -> list[dict[str, Any]]:
        ...


def parse_folder_guid(url: str) -> str:
    match = re.search(r"(?:enterprise_|folderGuid=|id=)([A-Za-z0-9_-]+)", url or "")
    if not match:
        raise BusinessError("INVALID_VDRIVE_URL", "无法从链接中解析 VDrive folderGuid")
    return match.group(1).removeprefix("enterprise_")


def normalize_file_info(raw: dict[str, Any], folder_path: str) -> dict[str, Any]:
    file_name = raw.get("FileName") or ""
    return {
        "vdrive_file_id": raw.get("FileId"),
        "file_guid": raw.get("FileGuid"),
        "file_name": file_name,
        "file_ext": raw.get("FileExtName"),
        "file_path": f"{folder_path.rstrip('/')}/{file_name}" if folder_path else file_name,
        "file_size": raw.get("FileLastSize") if raw.get("FileLastSize") is not None else raw.get("FileSize"),
        "file_version": raw.get("FileLastVerNumStr"),
        "created_time": raw.get("FileCreateTime"),
        "modified_time": None,
    }


class RealVDriveAdapter:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url if base_url is not None else settings.vdrive_base_url).rstrip("/")
        self.token = token if token is not None else settings.vdrive_token

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url or not self.token:
            raise BusinessError("VDRIVE_CONFIG_REQUIRED", "缺少 VDrive 地址或 token 配置")
        query = urllib.parse.urlencode({"token": self.token, **params})
        url = f"{self.base_url}/{path.lstrip('/')}?{query}"
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("result") != 0:
            raise BusinessError("VDRIVE_REQUEST_FAILED", payload.get("message") or "VDrive 接口调用失败")
        return payload

    def validate_folder_link(self, url: str) -> dict:
        guid = parse_folder_guid(url)
        payload = self._request("/api/services/Folder/GetFolderInfoByGuid", {"folderGuid": guid})
        data = payload.get("data") or {}
        if data.get("IsDeleted"):
            raise BusinessError("VDRIVE_FOLDER_DELETED", "VDrive 文件夹已删除")
        folder_id = data.get("FolderId")
        if folder_id is None:
            raise BusinessError("VDRIVE_FOLDER_NOT_FOUND", "未获取到 VDrive 文件夹 ID")
        return {
            "valid": True,
            "folder_guid": guid,
            "folder_id": folder_id,
            "folder_name": data.get("FolderName"),
            "folder_path": data.get("FolderPath"),
            "is_deleted": bool(data.get("IsDeleted", False)),
        }

    def list_folder_children(self, folder_id: int, page_num: int, page_size: int = 100) -> dict:
        payload = self._request(
            "/api/services/Doc/GetFileAndFolderList",
            {"folderId": folder_id, "pageNum": page_num, "pageSize": page_size},
        )
        return payload.get("data") or {}

    def list_files(self, folder_id: int, root_path: str | None = None) -> list[dict[str, Any]]:
        return self._list_files_recursive(folder_id, root_path or "")

    def _list_files_recursive(self, folder_id: int, folder_path: str) -> list[dict[str, Any]]:
        page_num = 1
        files: list[dict[str, Any]] = []
        while True:
            data = self.list_folder_children(folder_id, page_num, 100)
            files.extend(normalize_file_info(raw, folder_path) for raw in data.get("FilesInfo") or [] if not raw.get("IsDeleted"))
            for folder in data.get("FoldersInfo") or []:
                if folder.get("IsDeleted"):
                    continue
                child_path = f"{folder_path.rstrip('/')}/{folder.get('FolderName')}" if folder_path else folder.get("FolderName", "")
                files.extend(self._list_files_recursive(folder["FolderId"], child_path))
            settings_data = data.get("Settings") or {}
            page_size = int(settings_data.get("PageSize") or 100)
            total_count = int(settings_data.get("TotalCount") or 0)
            if page_num * page_size >= total_count:
                break
            page_num += 1
        return files


class MockVDriveAdapter:
    def __init__(self) -> None:
        self._folders_by_id: dict[int, dict[str, Any]] = {}

    def validate_folder_link(self, url: str) -> dict:
        guid = parse_folder_guid(url)
        folder_id = zlib.crc32(guid.encode("utf-8")) % 1_000_000_000
        folder = {
            "valid": True,
            "folder_guid": guid,
            "folder_id": folder_id,
            "folder_name": f"VDrive-{guid}",
            "folder_path": f"/mock/{guid}",
            "is_deleted": False,
        }
        self._folders_by_id[folder_id] = folder
        return folder

    def list_folder_children(self, folder_id: int, page_num: int, page_size: int = 100) -> dict:
        folder = self._folders_by_id.get(folder_id, {"folder_guid": str(folder_id), "folder_path": f"/mock/{folder_id}"})
        guid = folder["folder_guid"]
        if page_num > 1:
            return {"Settings": {"PageNum": page_num, "PageSize": page_size, "TotalCount": 0}, "FilesInfo": [], "FoldersInfo": []}
        if guid == "candidate-root":
            child_id = zlib.crc32(f"{guid}:qg3".encode("utf-8")) % 1_000_000_000
            self._folders_by_id[child_id] = {"folder_guid": f"{guid}/QG3", "folder_path": f"{folder['folder_path']}/QG3"}
            return {
                "Settings": {"PageNum": 1, "PageSize": page_size, "TotalCount": 1},
                "FilesInfo": [],
                "FoldersInfo": [
                    {
                        "FolderId": child_id,
                        "ParentFolderId": folder_id,
                        "FolderName": "QG3",
                        "FolderChildFoldersCount": 1,
                        "FolderChildFilesCount": 0,
                        "FolderCreateTime": "2026-06-01 09:00:00",
                        "IsDeleted": False,
                    }
                ],
            }
        if guid == "candidate-root/QG3":
            child_id = zlib.crc32(f"{guid}:pfmea".encode("utf-8")) % 1_000_000_000
            self._folders_by_id[child_id] = {"folder_guid": f"{guid}/PFMEA", "folder_path": f"{folder['folder_path']}/PFMEA"}
            return {
                "Settings": {"PageNum": 1, "PageSize": page_size, "TotalCount": 1},
                "FilesInfo": [],
                "FoldersInfo": [
                    {
                        "FolderId": child_id,
                        "ParentFolderId": folder_id,
                        "FolderName": "PFMEA",
                        "FolderChildFoldersCount": 0,
                        "FolderChildFilesCount": 2,
                        "FolderCreateTime": "2026-06-01 09:00:00",
                        "IsDeleted": False,
                    }
                ],
            }
        files = [
            {
                "FileId": 9001,
                "FileGuid": "file-guid-pfmea-v3",
                "ParentFolderId": folder_id,
                "FileLastVerNumStr": "3.0",
                "FileName": "PFMEA_V3.xlsx",
                "FileExtName": ".xlsx",
                "FileLastSize": 203456,
                "FileCreateTime": "2026-06-25 18:00:00",
                "IsDeleted": False,
            },
            {
                "FileId": 9002,
                "FileGuid": "file-guid-pfmea-v2",
                "ParentFolderId": folder_id,
                "FileLastVerNumStr": "2.0",
                "FileName": "PFMEA_V2.xlsx",
                "FileExtName": ".xlsx",
                "FileLastSize": 198000,
                "FileCreateTime": "2026-06-20 18:00:00",
                "IsDeleted": False,
            },
        ]
        return {"Settings": {"PageNum": 1, "PageSize": page_size, "TotalCount": len(files)}, "FilesInfo": files, "FoldersInfo": []}

    def list_files(self, folder_id: int, root_path: str | None = None) -> list[dict[str, Any]]:
        return self._list_files_recursive(folder_id, root_path or self._folders_by_id.get(folder_id, {}).get("folder_path", ""))

    def _list_files_recursive(self, folder_id: int, folder_path: str) -> list[dict[str, Any]]:
        page_num = 1
        files: list[dict[str, Any]] = []
        while True:
            data = self.list_folder_children(folder_id, page_num, 100)
            files.extend(normalize_file_info(raw, folder_path) for raw in data.get("FilesInfo") or [] if not raw.get("IsDeleted"))
            for folder in data.get("FoldersInfo") or []:
                if folder.get("IsDeleted"):
                    continue
                child_path = f"{folder_path.rstrip('/')}/{folder.get('FolderName')}" if folder_path else folder.get("FolderName", "")
                files.extend(self._list_files_recursive(folder["FolderId"], child_path))
            settings_data = data.get("Settings") or {}
            page_size = int(settings_data.get("PageSize") or 100)
            total_count = int(settings_data.get("TotalCount") or 0)
            if page_num * page_size >= total_count:
                break
            page_num += 1
        return files


def default_vdrive_adapter() -> VDriveAdapter:
    if settings.vdrive_base_url and settings.vdrive_token:
        return RealVDriveAdapter()
    return MockVDriveAdapter()


def validate_vdrive_folder_link(url: str, adapter: VDriveAdapter | None = None) -> dict:
    return (adapter or default_vdrive_adapter()).validate_folder_link(url)


def list_vdrive_files(folder_id: int, root_path: str | None = None, adapter: VDriveAdapter | None = None) -> list[dict[str, Any]]:
    return (adapter or default_vdrive_adapter()).list_files(folder_id, root_path)
