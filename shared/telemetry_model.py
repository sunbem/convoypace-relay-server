"""
shared/telemetry_model.py - Data model and binary layout for ETS2 SCS Telemetry.
Matches the official scs-telemetry-common.hpp structure (Local\\SCSTelemetry).
"""

from dataclasses import dataclass, field, asdict
import struct
from typing import Optional, Dict, Any

# SCS Shared Memory Constants
SCS_MMF_NAME = r"Local\SCSTelemetry"
SCS_MMF_SIZE = 32 * 1024  # 32 KB

# Byte Offsets from scs-telemetry-common.hpp
OFFSET_SDK_ACTIVE = 0           # bool (1 byte)
OFFSET_PAUSED = 4               # bool (1 byte)
OFFSET_TIMESTAMP = 8            # unsigned long long (8 bytes)

# Zone 4 (Floats, starts at 700)
# truck_f begins at 948
OFFSET_SPEED = 948              # float m/s
OFFSET_ROUTE_DISTANCE = 1060    # float meters
OFFSET_ROUTE_TIME = 1064        # float seconds
OFFSET_SPEED_LIMIT = 1068       # float m/s
OFFSET_CARGO_DAMAGE = 1260      # float (0.0 to 1.0)

# Zone 9 (Strings of length 64, starts at 2300)
OFFSET_CARGO_NAME = 2620        # char[64]
OFFSET_CITY_DST = 2748          # char[64]
OFFSET_COMP_DST = 2876          # char[64]
OFFSET_CITY_SRC = 3004          # char[64]
OFFSET_COMP_SRC = 3132          # char[64]

# Zone 12 (Special Events bools, starts at 4300)
OFFSET_ON_JOB = 4300            # bool
OFFSET_JOB_FINISHED = 4301      # bool
OFFSET_JOB_CANCELLED = 4302     # bool
OFFSET_JOB_DELIVERED = 4303     # bool


def clean_string(raw_bytes: bytes) -> str:
    """Helper to decode null-terminated or zero-padded C strings."""
    try:
        null_idx = raw_bytes.find(b"\x00")
        if null_idx != -1:
            raw_bytes = raw_bytes[:null_idx]
        return raw_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


@dataclass
class TelemetryData:
    sdk_active: bool = False
    paused: bool = False
    speed_ms: float = 0.0           # Speed in m/s
    route_distance_m: float = 0.0   # Remaining distance in meters
    route_time_s: float = 0.0       # Remaining time in seconds
    speed_limit_ms: float = 0.0     # Speed limit in m/s
    cargo_damage: float = 0.0       # 0.0 to 1.0 (e.g. 0.04 = 4%)
    destination_city: str = ""
    destination_company: str = ""
    source_city: str = ""
    source_company: str = ""
    cargo_name: str = ""
    on_job: bool = False
    job_finished: bool = False
    timestamp: float = 0.0

    @property
    def speed_kmh(self) -> float:
        """Speed in kilometers per hour."""
        return max(0.0, self.speed_ms * 3.6)

    @property
    def speed_mph(self) -> float:
        """Speed in miles per hour."""
        return max(0.0, self.speed_ms * 2.23694)

    @property
    def distance_km(self) -> float:
        """Remaining distance in kilometers."""
        return max(0.0, self.route_distance_m / 1000.0)

    @property
    def distance_mi(self) -> float:
        """Remaining distance in miles."""
        return max(0.0, self.route_distance_m * 0.000621371)

    @property
    def is_finished(self) -> bool:
        """Check if destination reached or job finished."""
        return (self.job_finished or 
                (self.on_job and self.route_distance_m <= 15.0 and self.speed_kmh < 5.0) or
                (self.on_job and self.route_distance_m <= 0.0))

    def format_distance(self, unit: str = "km") -> str:
        """Format remaining distance string."""
        if self.is_finished:
            return "🏁 FINISHED"
        if not self.on_job or self.route_distance_m <= 0:
            return "No Job / Free Roam"
        if unit.lower() == "mi":
            return f"{round(self.distance_mi)} mi"
        return f"{round(self.distance_km)} km"

    def format_speed(self, unit: str = "km") -> str:
        """Format current speed string."""
        if unit.lower() == "mi":
            return f"{round(self.speed_mph)} mph"
        return f"{round(self.speed_kmh)} km/h"

    def format_time(self) -> str:
        """Format remaining time as 'Xh Ym'."""
        if self.route_time_s <= 0 or not self.on_job:
            return "--:--"
        hours = int(self.route_time_s // 3600)
        minutes = int((self.route_time_s % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary for WebSocket broadcast."""
        d = asdict(self)
        d["speed_kmh"] = round(self.speed_kmh, 1)
        d["speed_mph"] = round(self.speed_mph, 1)
        d["distance_km"] = round(self.distance_km, 1)
        d["distance_mi"] = round(self.distance_mi, 1)
        d["time_formatted"] = self.format_time()
        d["is_finished"] = self.is_finished
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryData":
        """Instantiate from dictionary."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


def parse_telemetry_buffer(raw: bytes) -> Optional[TelemetryData]:
    """Parse raw bytes from Local\\SCSTelemetry memory block."""
    if len(raw) < SCS_MMF_SIZE:
        return None

    try:
        sdk_active = bool(struct.unpack_from("<?", raw, OFFSET_SDK_ACTIVE)[0])
        paused = bool(struct.unpack_from("<?", raw, OFFSET_PAUSED)[0])
        
        # Floats
        speed_ms = struct.unpack_from("<f", raw, OFFSET_SPEED)[0]
        route_distance_m = struct.unpack_from("<f", raw, OFFSET_ROUTE_DISTANCE)[0]
        route_time_s = struct.unpack_from("<f", raw, OFFSET_ROUTE_TIME)[0]
        speed_limit_ms = struct.unpack_from("<f", raw, OFFSET_SPEED_LIMIT)[0]
        cargo_damage = struct.unpack_from("<f", raw, OFFSET_CARGO_DAMAGE)[0]

        # Strings (64 bytes each)
        cargo_name = clean_string(raw[OFFSET_CARGO_NAME : OFFSET_CARGO_NAME + 64])
        city_dst = clean_string(raw[OFFSET_CITY_DST : OFFSET_CITY_DST + 64])
        comp_dst = clean_string(raw[OFFSET_COMP_DST : OFFSET_COMP_DST + 64])
        city_src = clean_string(raw[OFFSET_CITY_SRC : OFFSET_CITY_SRC + 64])
        comp_src = clean_string(raw[OFFSET_COMP_SRC : OFFSET_COMP_SRC + 64])

        # Special events
        on_job = bool(struct.unpack_from("<?", raw, OFFSET_ON_JOB)[0])
        job_finished = bool(struct.unpack_from("<?", raw, OFFSET_JOB_FINISHED)[0])

        return TelemetryData(
            sdk_active=sdk_active,
            paused=paused,
            speed_ms=max(0.0, speed_ms),
            route_distance_m=max(0.0, route_distance_m),
            route_time_s=max(0.0, route_time_s),
            speed_limit_ms=max(0.0, speed_limit_ms),
            cargo_damage=max(0.0, cargo_damage),
            destination_city=city_dst,
            destination_company=comp_dst,
            source_city=city_src,
            source_company=comp_src,
            cargo_name=cargo_name,
            on_job=on_job,
            job_finished=job_finished
        )
    except Exception as e:
        return None


def pack_telemetry_buffer(data: TelemetryData) -> bytearray:
    """Generate a valid 32KB binary buffer mimicking Local\\SCSTelemetry for tests and mock mode."""
    buf = bytearray(SCS_MMF_SIZE)

    struct.pack_into("<?", buf, OFFSET_SDK_ACTIVE, data.sdk_active)
    struct.pack_into("<?", buf, OFFSET_PAUSED, data.paused)
    
    struct.pack_into("<f", buf, OFFSET_SPEED, data.speed_ms)
    struct.pack_into("<f", buf, OFFSET_ROUTE_DISTANCE, data.route_distance_m)
    struct.pack_into("<f", buf, OFFSET_ROUTE_TIME, data.route_time_s)
    struct.pack_into("<f", buf, OFFSET_SPEED_LIMIT, data.speed_limit_ms)
    struct.pack_into("<f", buf, OFFSET_CARGO_DAMAGE, data.cargo_damage)

    def write_str(offset: int, s: str, max_len: int = 64):
        encoded = s.encode("utf-8")[: max_len - 1]
        buf[offset : offset + len(encoded)] = encoded
        buf[offset + len(encoded)] = 0

    write_str(OFFSET_CARGO_NAME, data.cargo_name)
    write_str(OFFSET_CITY_DST, data.destination_city)
    write_str(OFFSET_COMP_DST, data.destination_company)
    write_str(OFFSET_CITY_SRC, data.source_city)
    write_str(OFFSET_COMP_SRC, data.source_company)

    struct.pack_into("<?", buf, OFFSET_ON_JOB, data.on_job)
    struct.pack_into("<?", buf, OFFSET_JOB_FINISHED, data.job_finished)

    return buf

