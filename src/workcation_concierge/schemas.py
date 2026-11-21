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

"""Pydantic v2 data contracts for the Workcation & Smart Travel Concierge."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    """Structured travel and workcation request extracted from user input."""

    city: str = Field(
        description="Destination city slug (e.g., 'sapporo', 'okinawa', 'hawaii', 'san_francisco')."
    )
    nights: int = Field(
        default=2,
        ge=1,
        le=30,
        description="Number of hotel nights.",
    )
    flight_class: Literal["economy", "business"] = Field(
        default="economy",
        description="Requested flight class ('economy' or 'business').",
    )
    room_type: Literal["standard", "suite"] = Field(
        default="standard",
        description="Requested hotel room grade ('standard' or 'suite').",
    )
    purpose: str = Field(
        default="workcation",
        description="Business or workcation trip purpose.",
    )


class CandidatePlan(BaseModel):
    """Candidate flight and hotel option selected by the search specialist."""

    city: str = Field(description="Normalized destination city slug.")
    nights: int = Field(default=2, ge=1, description="Number of nights.")
    flight_code: str = Field(
        default="NH-051",
        description="Selected flight identifier.",
    )
    flight_class: Literal["economy", "business"] = Field(
        default="economy",
        description="Selected flight cabin class.",
    )
    hotel_name: str = Field(
        default="Workcation Hub Hotel",
        description="Selected hotel property name.",
    )
    room_type: Literal["standard", "suite"] = Field(
        default="standard",
        description="Selected hotel room grade.",
    )
    notes: str = Field(
        default="",
        description="Brief summary of selected flight and hotel options.",
    )


class ApprovalDecision(BaseModel):
    """Manager approval response payload for Human-in-the-Loop (RequestInput)."""

    approved: bool = Field(description="True if the manager approves the budget override.")
    approved_limit_jpy: int = Field(
        default=250000,
        ge=0,
        description="Updated maximum budget limit in JPY granted by the manager.",
    )
    approver_comment: str = Field(
        default="",
        description="Reason or condition recorded by the approving manager.",
    )


class BookingResult(BaseModel):
    """Final itinerary reservation outcome."""

    status: Literal["CONFIRMED", "BLOCKED", "NEEDS_REPLAN"] = Field(
        description="Final reservation status."
    )
    reservation_id: str = Field(
        default="",
        description="Confirmation identifier when status is CONFIRMED.",
    )
    city: str = Field(description="Destination city slug.")
    nights: int = Field(description="Number of nights booked.")
    flight_class: str = Field(default="economy", description="Booked flight class.")
    room_type: str = Field(default="standard", description="Booked hotel room type.")
    total_jpy: int = Field(description="Total itinerary cost in JPY.")
    wifi_mbps: int = Field(default=100, description="Verified hotel/city Wi-Fi speed in Mbps.")
    summary: str = Field(default="", description="Human-readable confirmation summary.")
