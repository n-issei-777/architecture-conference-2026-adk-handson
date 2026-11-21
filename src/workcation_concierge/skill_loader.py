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

"""Helper for loading the corporate travel-policy skill into an ADK SkillToolset."""

from __future__ import annotations

from pathlib import Path

from google.adk.skills import Skill, load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

# リポジトリルートの skills/travel-policy ディレクトリへのパス解決
REPO_ROOT = Path(__file__).resolve().parents[2]
TRAVEL_POLICY_SKILL_DIR = REPO_ROOT / "skills" / "travel-policy"


def load_travel_policy_skill(skill_dir: Path | None = None) -> Skill:
    """Load the `travel-policy` ADK Skill definition from disk."""
    target_dir = skill_dir or TRAVEL_POLICY_SKILL_DIR
    return load_skill_from_dir(target_dir)


def create_travel_policy_skill_toolset(skill_dir: Path | None = None) -> SkillToolset:
    """Create a `SkillToolset` pre-populated with the `travel-policy` skill."""
    skill = load_travel_policy_skill(skill_dir=skill_dir)
    return SkillToolset(skills=[skill])
