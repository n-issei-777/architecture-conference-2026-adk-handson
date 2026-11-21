---
name: travel-policy
description: Corporate workcation and business travel policy rules covering connectivity requirements, cabin/room grade restrictions, and budget approval thresholds.
---

# Corporate Workcation & Business Travel Policy

Always follow these corporate travel and workcation compliance rules when planning or booking itineraries:

## 1. Workcation Connectivity Requirements
- Remote work / workcation destinations MUST provide reliable hotel and coworking internet connectivity of **at least 50 Mbps** (`wifi_mbps >= 50`).
- Verify connectivity metrics before finalizing a workcation hotel.

## 2. Cabin Class & Room Grade Restrictions
- **Standard Employees (`user_role = "member"`)**:
  - Flights: **Economy class (`economy`) only**. Business class (`business`) is strictly prohibited.
  - Hotels: **Standard rooms (`standard`) only**. Suite rooms (`suite`) are strictly prohibited.
- **Executives (`user_role = "executive"`)**:
  - Permitted to book `business` flights and `suite` rooms when justified by business schedule.

## 3. Budget Thresholds & Approval Escalation
- **Self-Approval Limit (`DEFAULT_APPROVED_LIMIT_JPY`)**: **150,000 JPY** total per trip (round-trip flight + all hotel nights combined).
- **Trips `<= 150,000 JPY`**:
  - May be booked automatically (`auto_book`) without manager intervention, provided grade and connectivity rules are satisfied.
- **Trips `> 150,000 JPY`**:
  - Cannot be booked directly at the default limit.
  - Require **Manager Approval (`needs_approval`)** to raise `Session.state["approved_limit_jpy"]` (for example, up to `250,000 JPY` for international or multi-night workcations such as Hawaii).
  - Even with a manager budget override, standard employees (`member`) must still book `economy` flights and `standard` rooms.
