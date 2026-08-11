from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

@dataclass
class VNyanInstance:
    executable_path: Path | None
    pid: int | None
    host: str
    api_port: int | None
    vmc_port: int | None
    osc_port: int | None
    running: bool
    version: str | None

@dataclass
class AvatarExpressionProfile:
    available: list[str] = field(default_factory=list)

    viseme_a: str | None = None
    viseme_e: str | None = None
    viseme_i: str | None = None
    viseme_o: str | None = None
    viseme_u: str | None = None

    happy: str | None = None
    sad: str | None = None
    angry: str | None = None
    surprised: str | None = None
    relaxed: str | None = None
    neutral: str | None = None

    blink: str | None = None
    blink_left: str | None = None
    blink_right: str | None = None

    custom: list[str] = field(default_factory=list)

@dataclass
class AvatarProfile:
    source_path: Path
    format: str
    version: str
    height: float | None
    bones: int
    materials: int
    textures: int
    expressions: AvatarExpressionProfile
    detected_at: datetime

@dataclass
class VNyanHealth:
    process: bool = False
    api: bool = False
    vmc: bool = False
    avatar: bool = False
    blendshape: bool = False
    viseme: bool = False
    emotion: bool = False
    blink: bool = False
    event_bridge: bool = False
    node_graph: bool = False

    @property
    def ready(self) -> bool:
        """Kiểm định cổng sẵn sàng (Ready Gate) nghiêm ngặt yêu cầu tất cả các năng lực và tiến trình hoạt động."""
        return (
            self.process
            and self.api
            and self.vmc
            and self.avatar
            and self.blendshape
            and self.viseme
            and self.emotion
            and self.blink
            and self.event_bridge
            and self.node_graph
        )

@dataclass
class SetupResult:
    success: bool
    status: str  # NOT_FOUND, STARTING, CONFIGURING, TESTING, READY, DEGRADED, FAILED, ROLLED_BACK
    avatar_profile: AvatarProfile | None
    health: VNyanHealth
    changes: list[str]
    warnings: list[str]
    errors: list[str]
    rollback_available: bool
