# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""FastMCP server (travel-saas-mcp) and deterministic catalog functions."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer as FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# MCPサーバーのインスタンス定義
mcp = FastMCP("travel-saas-mcp")

# 都市別の確定カタログデータ
# - sapporo: 2泊 economy(35,000) + standard(12,000 * 2 = 24,000) = 59,000 JPY (<= 150,000 JPY)
# - okinawa: 3泊 economy(45,000) + standard(16,000 * 3 = 48,000) = 93,000 JPY (<= 150,000 JPY)
# - hawaii:  4泊 economy(130,000) + standard(28,000 * 4 = 112,000) = 242,000 JPY (> 150,000 JPY)
# - san_francisco: 4泊 economy(180,000) + standard(35,000 * 4) = 320,000 JPY (> 150,000 JPY)
_CITY_CATALOG: dict[str, dict[str, Any]] = {
    "sapporo": {
        "display_name": "Sapporo",
        "wifi_mbps": 120,
        "coworking_spaces": 14,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "NH-051", "round_trip_jpy": 35000},
            "business": {"flight_code": "NH-051-C", "round_trip_jpy": 80000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Sapporo Workcation Hub Hotel",
                "per_night_jpy": 12000,
                "wifi_mbps": 120,
            },
            "suite": {
                "hotel_name": "Sapporo Grand Executive Suite",
                "per_night_jpy": 40000,
                "wifi_mbps": 150,
            },
        },
    },
    "okinawa": {
        "display_name": "Okinawa (Naha)",
        "wifi_mbps": 110,
        "coworking_spaces": 11,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "JL-901", "round_trip_jpy": 45000},
            "business": {"flight_code": "JL-901-C", "round_trip_jpy": 95000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Okinawa Oceanfront Work Hotel",
                "per_night_jpy": 16000,
                "wifi_mbps": 110,
            },
            "suite": {
                "hotel_name": "Okinawa Royal Villa Suite",
                "per_night_jpy": 52000,
                "wifi_mbps": 140,
            },
        },
    },
    "hawaii": {
        "display_name": "Honolulu (Hawaii)",
        "wifi_mbps": 95,
        "coworking_spaces": 9,
        "timezone_offset": "UTC-10",
        "flights": {
            "economy": {"flight_code": "HA-864", "round_trip_jpy": 130000},
            "business": {"flight_code": "HA-864-C", "round_trip_jpy": 340000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Waikiki Business & Surf Hotel",
                "per_night_jpy": 28000,
                "wifi_mbps": 95,
            },
            "suite": {
                "hotel_name": "Waikiki Ocean Penthouse Suite",
                "per_night_jpy": 85000,
                "wifi_mbps": 130,
            },
        },
    },
    "san_francisco": {
        "display_name": "San Francisco",
        "wifi_mbps": 180,
        "coworking_spaces": 28,
        "timezone_offset": "UTC-8",
        "flights": {
            "economy": {"flight_code": "UA-838", "round_trip_jpy": 180000},
            "business": {"flight_code": "UA-838-C", "round_trip_jpy": 480000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "SoMa Tech Hub Inn",
                "per_night_jpy": 35000,
                "wifi_mbps": 180,
            },
            "suite": {
                "hotel_name": "Bay Area Executive Tower Suite",
                "per_night_jpy": 95000,
                "wifi_mbps": 220,
            },
        },
    },
    "tokyo": {
        "display_name": "Tokyo",
        "wifi_mbps": 200,
        "coworking_spaces": 45,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "NH-001", "round_trip_jpy": 24000},
            "business": {"flight_code": "NH-001-C", "round_trip_jpy": 58000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Tokyo Tech Work Hub Hotel",
                "per_night_jpy": 18000,
                "wifi_mbps": 200,
            },
            "suite": {
                "hotel_name": "Tokyo Bay Executive Suite",
                "per_night_jpy": 55000,
                "wifi_mbps": 250,
            },
        },
    },
    "osaka": {
        "display_name": "Osaka",
        "wifi_mbps": 150,
        "coworking_spaces": 24,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "JL-107", "round_trip_jpy": 26000},
            "business": {"flight_code": "JL-107-C", "round_trip_jpy": 62000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Osaka Umeda Workcation Hotel",
                "per_night_jpy": 14000,
                "wifi_mbps": 150,
            },
            "suite": {
                "hotel_name": "Osaka Imperial Sky Suite",
                "per_night_jpy": 46000,
                "wifi_mbps": 180,
            },
        },
    },
    "kyoto": {
        "display_name": "Kyoto",
        "wifi_mbps": 130,
        "coworking_spaces": 16,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "JL-109", "round_trip_jpy": 28000},
            "business": {"flight_code": "JL-109-C", "round_trip_jpy": 65000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Kyoto Machiya Work Retreat",
                "per_night_jpy": 16000,
                "wifi_mbps": 130,
            },
            "suite": {
                "hotel_name": "Kyoto Higashiyama Villa Suite",
                "per_night_jpy": 50000,
                "wifi_mbps": 160,
            },
        },
    },
    "fukuoka": {
        "display_name": "Fukuoka",
        "wifi_mbps": 160,
        "coworking_spaces": 20,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "NH-245", "round_trip_jpy": 34000},
            "business": {"flight_code": "NH-245-C", "round_trip_jpy": 78000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Fukuoka Tenjin Startup Hotel",
                "per_night_jpy": 13000,
                "wifi_mbps": 160,
            },
            "suite": {
                "hotel_name": "Fukuoka Hakata Executive Suite",
                "per_night_jpy": 42000,
                "wifi_mbps": 200,
            },
        },
    },
    "nagoya": {
        "display_name": "Nagoya",
        "wifi_mbps": 140,
        "coworking_spaces": 15,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "NH-085", "round_trip_jpy": 22000},
            "business": {"flight_code": "NH-085-C", "round_trip_jpy": 54000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Nagoya Station Business Lounge Hotel",
                "per_night_jpy": 12000,
                "wifi_mbps": 140,
            },
            "suite": {
                "hotel_name": "Nagoya Central Tower Suite",
                "per_night_jpy": 38000,
                "wifi_mbps": 170,
            },
        },
    },
    "sendai": {
        "display_name": "Sendai",
        "wifi_mbps": 125,
        "coworking_spaces": 10,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "JL-2201", "round_trip_jpy": 26000},
            "business": {"flight_code": "JL-2201-C", "round_trip_jpy": 60000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Sendai Mori-no-Miyako Work Hotel",
                "per_night_jpy": 11000,
                "wifi_mbps": 125,
            },
            "suite": {
                "hotel_name": "Sendai Grand Executive Suite",
                "per_night_jpy": 36000,
                "wifi_mbps": 150,
            },
        },
    },
    "kanazawa": {
        "display_name": "Kanazawa",
        "wifi_mbps": 115,
        "coworking_spaces": 9,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "NH-751", "round_trip_jpy": 30000},
            "business": {"flight_code": "NH-751-C", "round_trip_jpy": 68000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Kanazawa Heritage Work Hotel",
                "per_night_jpy": 13000,
                "wifi_mbps": 115,
            },
            "suite": {
                "hotel_name": "Kanazawa Kenroku Villa Suite",
                "per_night_jpy": 42000,
                "wifi_mbps": 140,
            },
        },
    },
    "karuizawa": {
        "display_name": "Karuizawa",
        "wifi_mbps": 100,
        "coworking_spaces": 8,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "EX-511", "round_trip_jpy": 14000},
            "business": {"flight_code": "EX-511-C", "round_trip_jpy": 32000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Karuizawa Forest Work Lodge",
                "per_night_jpy": 19000,
                "wifi_mbps": 100,
            },
            "suite": {
                "hotel_name": "Karuizawa Highland Resort Suite",
                "per_night_jpy": 54000,
                "wifi_mbps": 130,
            },
        },
    },
    "seoul": {
        "display_name": "Seoul",
        "wifi_mbps": 220,
        "coworking_spaces": 32,
        "timezone_offset": "UTC+9",
        "flights": {
            "economy": {"flight_code": "KE-704", "round_trip_jpy": 72000},
            "business": {"flight_code": "KE-704-C", "round_trip_jpy": 185000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Seoul Gangnam Tech Hub Hotel",
                "per_night_jpy": 22000,
                "wifi_mbps": 220,
            },
            "suite": {
                "hotel_name": "Seoul Namsan Executive Suite",
                "per_night_jpy": 68000,
                "wifi_mbps": 260,
            },
        },
    },
    "taipei": {
        "display_name": "Taipei",
        "wifi_mbps": 170,
        "coworking_spaces": 22,
        "timezone_offset": "UTC+8",
        "flights": {
            "economy": {"flight_code": "BR-197", "round_trip_jpy": 78000},
            "business": {"flight_code": "BR-197-C", "round_trip_jpy": 195000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Taipei Xinyi Digital Nomad Hotel",
                "per_night_jpy": 21000,
                "wifi_mbps": 170,
            },
            "suite": {
                "hotel_name": "Taipei 101 View Penthouse Suite",
                "per_night_jpy": 64000,
                "wifi_mbps": 200,
            },
        },
    },
    "bangkok": {
        "display_name": "Bangkok",
        "wifi_mbps": 145,
        "coworking_spaces": 26,
        "timezone_offset": "UTC+7",
        "flights": {
            "economy": {"flight_code": "TG-641", "round_trip_jpy": 95000},
            "business": {"flight_code": "TG-641-C", "round_trip_jpy": 260000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Bangkok Sukhumvit Work Hotel",
                "per_night_jpy": 18000,
                "wifi_mbps": 145,
            },
            "suite": {
                "hotel_name": "Bangkok Chao Phraya Grand Suite",
                "per_night_jpy": 58000,
                "wifi_mbps": 180,
            },
        },
    },
    "singapore": {
        "display_name": "Singapore",
        "wifi_mbps": 210,
        "coworking_spaces": 30,
        "timezone_offset": "UTC+8",
        "flights": {
            "economy": {"flight_code": "SQ-637", "round_trip_jpy": 115000},
            "business": {"flight_code": "SQ-637-C", "round_trip_jpy": 320000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "Singapore Marina Tech Hotel",
                "per_night_jpy": 30000,
                "wifi_mbps": 210,
            },
            "suite": {
                "hotel_name": "Singapore Bayfront Executive Suite",
                "per_night_jpy": 90000,
                "wifi_mbps": 250,
            },
        },
    },
    "london": {
        "display_name": "London",
        "wifi_mbps": 165,
        "coworking_spaces": 38,
        "timezone_offset": "UTC+0",
        "flights": {
            "economy": {"flight_code": "BA-006", "round_trip_jpy": 210000},
            "business": {"flight_code": "BA-006-C", "round_trip_jpy": 560000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "London Shoreditch Work Inn",
                "per_night_jpy": 38000,
                "wifi_mbps": 165,
            },
            "suite": {
                "hotel_name": "London Mayfair Executive Suite",
                "per_night_jpy": 110000,
                "wifi_mbps": 200,
            },
        },
    },
    "new_york": {
        "display_name": "New York",
        "wifi_mbps": 190,
        "coworking_spaces": 42,
        "timezone_offset": "UTC-5",
        "flights": {
            "economy": {"flight_code": "JL-006", "round_trip_jpy": 220000},
            "business": {"flight_code": "JL-006-C", "round_trip_jpy": 590000},
        },
        "hotels": {
            "standard": {
                "hotel_name": "New York Midtown Workcation Hotel",
                "per_night_jpy": 42000,
                "wifi_mbps": 190,
            },
            "suite": {
                "hotel_name": "New York Manhattan Sky Suite",
                "per_night_jpy": 120000,
                "wifi_mbps": 230,
            },
        },
    },
}

# 都市名の表記ゆれ正規化マップ
_CITY_ALIASES: dict[str, str] = {
    "sapporo": "sapporo",
    "札幌": "sapporo",
    "北海道": "sapporo",
    "okinawa": "okinawa",
    "naha": "okinawa",
    "沖縄": "okinawa",
    "那覇": "okinawa",
    "hawaii": "hawaii",
    "honolulu": "hawaii",
    "ハワイ": "hawaii",
    "ホノルル": "hawaii",
    "san_francisco": "san_francisco",
    "san francisco": "san_francisco",
    "sfo": "san_francisco",
    "サンフランシスコ": "san_francisco",
    "tokyo": "tokyo",
    "東京": "tokyo",
    "東京都": "tokyo",
    "tyo": "tokyo",
    "osaka": "osaka",
    "大阪": "osaka",
    "大阪府": "osaka",
    "osa": "osaka",
    "kyoto": "kyoto",
    "京都": "kyoto",
    "京都府": "kyoto",
    "fukuoka": "fukuoka",
    "hakata": "fukuoka",
    "福岡": "fukuoka",
    "福岡県": "fukuoka",
    "博多": "fukuoka",
    "fuk": "fukuoka",
    "nagoya": "nagoya",
    "名古屋": "nagoya",
    "愛知": "nagoya",
    "愛知県": "nagoya",
    "ngo": "nagoya",
    "sendai": "sendai",
    "仙台": "sendai",
    "宮城": "sendai",
    "宮城県": "sendai",
    "kanazawa": "kanazawa",
    "金沢": "kanazawa",
    "石川": "kanazawa",
    "石川県": "kanazawa",
    "karuizawa": "karuizawa",
    "軽井沢": "karuizawa",
    "長野": "karuizawa",
    "長野県": "karuizawa",
    "seoul": "seoul",
    "korea": "seoul",
    "ソウル": "seoul",
    "韓国": "seoul",
    "icn": "seoul",
    "taipei": "taipei",
    "taiwan": "taipei",
    "台北": "taipei",
    "台湾": "taipei",
    "tpe": "taipei",
    "bangkok": "bangkok",
    "thailand": "bangkok",
    "バンコク": "bangkok",
    "タイ": "bangkok",
    "bkk": "bangkok",
    "singapore": "singapore",
    "シンガポール": "singapore",
    "sin": "singapore",
    "london": "london",
    "uk": "london",
    "ロンドン": "london",
    "イギリス": "london",
    "英国": "london",
    "lhr": "london",
    "new_york": "new_york",
    "new york": "new_york",
    "nyc": "new_york",
    "ny": "new_york",
    "jfk": "new_york",
    "ニューヨーク": "new_york",
}

# インメモリ予約台帳
_RESERVATION_LEDGER: list[dict[str, Any]] = []


def normalize_city(city: str) -> str:
    """Normalize a raw city name or Japanese label to a canonical catalog key."""
    cleaned = city.strip().lower()
    return _CITY_ALIASES.get(cleaned, cleaned)


def CLEAR_RESERVATIONS_FOR_TEST() -> None:
    """Reset the in-memory reservation ledger for hermetic unit testing."""
    _RESERVATION_LEDGER.clear()


@mcp.tool()
def search_flights(city: str) -> dict[str, Any]:
    """Search available round-trip flights for a destination city.

    Args:
        city: Destination city name (e.g., 'sapporo', 'okinawa', 'hawaii', 'san_francisco').

    Returns:
        Dictionary containing status and a list of available flight options in JPY.
    """
    norm_city = normalize_city(city)
    entry = _CITY_CATALOG.get(norm_city)
    if entry is None:
        return {
            "status": "error",
            "error_type": "UNSUPPORTED_CITY",
            "message": f"Unsupported destination city: '{city}'.",
            "supported_cities": sorted(_CITY_CATALOG.keys()),
        }

    flights_map = entry["flights"]
    return {
        "status": "ok",
        "city": norm_city,
        "display_name": entry["display_name"],
        "flights": [
            {
                "flight_class": flight_class,
                "flight_code": info["flight_code"],
                "round_trip_jpy": info["round_trip_jpy"],
            }
            for flight_class, info in flights_map.items()
        ],
    }


@mcp.tool()
def search_hotels(city: str) -> dict[str, Any]:
    """Search available workcation hotels and nightly rates for a destination city.

    Args:
        city: Destination city name (e.g., 'sapporo', 'okinawa', 'hawaii', 'san_francisco').

    Returns:
        Dictionary containing status and hotel options with nightly rates and Wi-Fi speeds.
    """
    norm_city = normalize_city(city)
    entry = _CITY_CATALOG.get(norm_city)
    if entry is None:
        return {
            "status": "error",
            "error_type": "UNSUPPORTED_CITY",
            "message": f"Unsupported destination city: '{city}'.",
            "supported_cities": sorted(_CITY_CATALOG.keys()),
        }

    hotels_map = entry["hotels"]
    return {
        "status": "ok",
        "city": norm_city,
        "display_name": entry["display_name"],
        "hotels": [
            {
                "room_type": room_type,
                "hotel_name": info["hotel_name"],
                "per_night_jpy": info["per_night_jpy"],
                "wifi_mbps": info["wifi_mbps"],
            }
            for room_type, info in hotels_map.items()
        ],
    }


@mcp.tool()
def fetch_workcation_metrics(city: str) -> dict[str, Any]:
    """Fetch remote-work connectivity and coworking metrics for a destination city.

    Args:
        city: Destination city name.

    Returns:
        Dictionary with Wi-Fi speed (Mbps), coworking space count, and policy compliance flag.
    """
    norm_city = normalize_city(city)
    entry = _CITY_CATALOG.get(norm_city)
    if entry is None:
        return {
            "status": "error",
            "error_type": "UNSUPPORTED_CITY",
            "message": f"Unsupported destination city: '{city}'.",
            "supported_cities": sorted(_CITY_CATALOG.keys()),
        }

    wifi_mbps = int(entry["wifi_mbps"])
    return {
        "status": "ok",
        "city": norm_city,
        "display_name": entry["display_name"],
        "wifi_mbps": wifi_mbps,
        "meets_wifi_policy": wifi_mbps >= 50,
        "coworking_spaces": int(entry["coworking_spaces"]),
        "timezone_offset": str(entry["timezone_offset"]),
    }


@mcp.tool()
def calculate_itinerary_cost(
    city: str,
    nights: int,
    flight_class: str = "economy",
    room_type: str = "standard",
) -> dict[str, Any]:
    """Deterministically calculate exact round-trip flight plus hotel cost in JPY.

    Args:
        city: Destination city name.
        nights: Number of hotel nights (must be >= 1).
        flight_class: 'economy' or 'business'.
        room_type: 'standard' or 'suite'.

    Returns:
        Structured dictionary with exact breakdown and total_jpy.
    """
    norm_city = normalize_city(city)
    entry = _CITY_CATALOG.get(norm_city)
    if entry is None:
        return {
            "status": "error",
            "error_type": "UNSUPPORTED_CITY",
            "message": f"Unsupported destination city: '{city}'.",
            "supported_cities": sorted(_CITY_CATALOG.keys()),
        }

    if nights < 1:
        return {
            "status": "error",
            "error_type": "INVALID_NIGHTS",
            "message": "Number of nights must be at least 1.",
        }

    norm_flight = flight_class.strip().lower()
    norm_room = room_type.strip().lower()
    if norm_flight not in entry["flights"]:
        return {
            "status": "error",
            "error_type": "INVALID_FLIGHT_CLASS",
            "message": f"Unsupported flight_class '{flight_class}'. Use 'economy' or 'business'.",
        }
    if norm_room not in entry["hotels"]:
        return {
            "status": "error",
            "error_type": "INVALID_ROOM_TYPE",
            "message": f"Unsupported room_type '{room_type}'. Use 'standard' or 'suite'.",
        }

    flight_info = entry["flights"][norm_flight]
    hotel_info = entry["hotels"][norm_room]
    flight_jpy = int(flight_info["round_trip_jpy"])
    hotel_per_night_jpy = int(hotel_info["per_night_jpy"])
    hotel_total_jpy = hotel_per_night_jpy * int(nights)
    total_jpy = flight_jpy + hotel_total_jpy

    return {
        "status": "ok",
        "city": norm_city,
        "display_name": entry["display_name"],
        "nights": int(nights),
        "flight_class": norm_flight,
        "flight_code": flight_info["flight_code"],
        "flight_jpy": flight_jpy,
        "room_type": norm_room,
        "hotel_name": hotel_info["hotel_name"],
        "hotel_per_night_jpy": hotel_per_night_jpy,
        "hotel_total_jpy": hotel_total_jpy,
        "wifi_mbps": int(hotel_info["wifi_mbps"]),
        "total_jpy": total_jpy,
    }


@mcp.tool()
def reserve_itinerary(
    city: str,
    nights: int,
    flight_class: str,
    room_type: str,
    total_jpy: int,
    purpose: str = "workcation",
) -> dict[str, Any]:
    """Execute itinerary reservation in the external Travel SaaS system.

    Note:
        This external SaaS tool does not know internal corporate policies.
        Client agents must attach `enforce_booking_guardrail` (`before_tool_callback`).

    Args:
        city: Destination city name.
        nights: Number of nights.
        flight_class: Flight cabin class ('economy' or 'business').
        room_type: Hotel room grade ('standard' or 'suite').
        total_jpy: Total itinerary price in JPY.
        purpose: Business purpose of the trip.

    Returns:
        Confirmation dictionary including reservation_id.
    """
    norm_city = normalize_city(city)
    reservation_id = f"RES-{norm_city[:3].upper()}-{len(_RESERVATION_LEDGER) + 1:04d}"
    record = {
        "status": "CONFIRMED",
        "reservation_id": reservation_id,
        "city": norm_city,
        "nights": int(nights),
        "flight_class": flight_class.strip().lower(),
        "room_type": room_type.strip().lower(),
        "total_jpy": int(total_jpy),
        "purpose": purpose,
    }
    _RESERVATION_LEDGER.append(record)
    return record


@mcp.tool()
def get_reservations() -> dict[str, Any]:
    """Return all confirmed reservations recorded in the Travel SaaS ledger."""
    return {
        "status": "ok",
        "count": len(_RESERVATION_LEDGER),
        "reservations": list(_RESERVATION_LEDGER),
    }


if __name__ == "__main__":
    # Cloud Run 等で MCP_TRANSPORT=streamable-http または PORT 指定時は HTTP モードで起動
    transport = os.getenv("MCP_TRANSPORT", "").strip().lower()
    if transport == "streamable-http" or (not transport and os.getenv("PORT")):
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8080")),
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
            ),
        )
    else:
        mcp.run()
