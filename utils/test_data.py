"""Reusable test-data builders.

Keeps dynamic value generation out of the test body and the page objects.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class UserRecord:
    user_role: str
    employee_name: str
    status: str
    username: str
    password: str

    def with_updates(
        self,
        *,
        user_role: str | None = None,
        status: str | None = None,
        username: str | None = None,
    ) -> "UserRecord":
        return replace(
            self,
            user_role=user_role or self.user_role,
            status=status or self.status,
            username=username or self.username,
        )


def unique_username(prefix: str = "qa_user") -> str:
    """Timestamp + short UUID keeps the value unique even across parallel runs."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}_{stamp}_{suffix}"


def build_new_user(employee_name: str) -> UserRecord:
    return UserRecord(
        user_role="Admin",
        employee_name=employee_name,
        status="Enabled",
        username=unique_username(),
        password="Passw0rd!_" + uuid.uuid4().hex[:4],
    )
