# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Defines the mapping from GitHub Team Name to a list of member GitHub logins.
# The first member in each list is considered the default assignee for issues.
TEAM_MEMBERS = {
    "technical-committee": ["nearlyforget", "tc_member2_user"],
    "governance-committee": ["nearlyforget", "gc_member2_user"],
    "maintainers": ["nearlyforget", "maintainer2_user"],
    "devops-maintainers": ["nearlyforget", "devops2_user"],
}
