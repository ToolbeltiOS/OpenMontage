"""Upload a caption track to a YouTube video (captions.insert).

WHY THIS IS A TOOL AND NOT A LINE IN THE UPLOADER
-------------------------------------------------
The film is no longer rendered with its narration burnt into the picture, so
the caption track is a separate deliverable with its own failure modes: a
track can be uploaded against the wrong video, in the wrong language, as a
draft nobody sees, or twice. Those are worth a contract and a dry run rather
than three lines inside a 300-line upload script.

It also means a caption can be fixed without re-rendering a twenty-minute
film, which was the whole point of moving off the burn.

SCOPES
------
`captions.insert` needs `https://www.googleapis.com/auth/youtube.force-ssl`.
An upload-only token will authenticate and then fail with an insufficient
permission error, which is reported as such rather than retried.
"""
from __future__ import annotations

import os
import time
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


class YouTubeCaptions(BaseTool):
    name = "youtube_captions"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publishing"
    provider = "youtube"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["pip:google-api-python-client", "pip:google-auth"]
    install_instructions = (
        "pip install google-api-python-client google-auth\n"
        "Authorise once with a token carrying the force-ssl scope:\n"
        f"  {SCOPE}\n"
        "Point YOUTUBE_OAUTH_TOKEN at the pickled credentials."
    )

    capabilities = ["upload_captions", "list_captions"]
    best_for = [
        "shipping a closed-caption track beside a long-form upload",
        "replacing a caption track without re-rendering the film",
    ]
    not_good_for = [
        "burning captions into the picture (that is the composer's job)",
        "translating captions",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_id", "srt_path"],
        "properties": {
            "video_id": {"type": "string"},
            "srt_path": {"type": "string"},
            "language": {"type": "string", "default": "en"},
            "name": {
                "type": "string",
                "default": "English",
                "description": "Track name shown in the player's caption menu.",
            },
            "is_draft": {
                "type": "boolean",
                "default": False,
                "description": "A draft track is uploaded but not served.",
            },
            "replace_existing": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Delete an existing track with the same language first. "
                    "Without it a second upload leaves two tracks and the "
                    "player picks one."
                ),
            },
            "token_path": {"type": "string"},
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "Validate everything and stop before the call.",
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0,
                                       disk_mb=10, network_required=True)
    retry_policy = RetryPolicy(max_retries=2)
    idempotency_key_fields = ["video_id", "srt_path", "language"]
    side_effects = ["uploads a caption track to a YouTube video"]
    user_visible_verification = [
        "Open the video and confirm the CC button offers the track",
        "Check the track is not listed as a draft in Studio",
    ]

    def get_status(self) -> ToolStatus:
        try:
            import googleapiclient  # noqa: F401
        except ImportError:
            return ToolStatus.UNAVAILABLE
        # DEGRADED rather than UNAVAILABLE without a token: the tool is
        # installed and its dry run works, which is what the publish rehearsal
        # needs before anyone authorises a write scope.
        return ToolStatus.AVAILABLE if self._token_path() else ToolStatus.DEGRADED

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    @staticmethod
    def _token_path(explicit: str | None = None) -> str | None:
        path = explicit or os.environ.get("YOUTUBE_OAUTH_TOKEN", "")
        return path if path and os.path.exists(os.path.expanduser(path)) else None

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        srt = os.path.expanduser(inputs["srt_path"])
        if not os.path.exists(srt):
            return ToolResult(success=False, error=f"no caption file at {srt}")
        if os.path.getsize(srt) == 0:
            return ToolResult(success=False, error=f"caption file is empty: {srt}")

        body = {
            "snippet": {
                "videoId": inputs["video_id"],
                "language": inputs.get("language", "en"),
                "name": inputs.get("name", "English"),
                "isDraft": bool(inputs.get("is_draft", False)),
            }
        }
        # The dry run is checked before the token, deliberately: rehearsing a
        # publish is exactly what you want to do BEFORE anyone authorises a
        # write scope on the channel.
        if inputs.get("dry_run"):
            return ToolResult(
                success=True,
                data={"dry_run": True, "body": body, "srt_bytes": os.path.getsize(srt)},
                duration_seconds=round(time.time() - start, 2),
            )

        token = self._token_path(inputs.get("token_path"))
        if not token:
            return ToolResult(success=False,
                              error="no OAuth token. " + self.install_instructions)

        try:
            import pickle

            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            with open(os.path.expanduser(token), "rb") as fh:
                creds = pickle.load(fh)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            if getattr(creds, "scopes", None) and SCOPE not in creds.scopes:
                return ToolResult(
                    success=False,
                    error=(f"this token does not carry {SCOPE}; captions.insert "
                           f"will be refused. Re-authorise with that scope."))
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

            removed = []
            if inputs.get("replace_existing"):
                existing = yt.captions().list(
                    part="snippet", videoId=inputs["video_id"]).execute()
                for item in existing.get("items", []):
                    if item["snippet"]["language"] == body["snippet"]["language"]:
                        yt.captions().delete(id=item["id"]).execute()
                        removed.append(item["id"])

            media = MediaFileUpload(srt, mimetype="application/octet-stream",
                                    resumable=False)
            resp = yt.captions().insert(part="snippet", body=body,
                                        media_body=media).execute()
        except Exception as exc:  # pragma: no cover - network path
            return ToolResult(success=False, error=f"captions.insert failed: {exc}",
                              duration_seconds=round(time.time() - start, 2))

        return ToolResult(
            success=True,
            data={
                "caption_id": resp.get("id"),
                "video_id": inputs["video_id"],
                "language": body["snippet"]["language"],
                "name": body["snippet"]["name"],
                "is_draft": body["snippet"]["isDraft"],
                "replaced": removed,
                "srt_bytes": os.path.getsize(srt),
            },
            artifacts=[srt],
            duration_seconds=round(time.time() - start, 2),
        )
