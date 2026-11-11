"""Show or change a user's role. This is how the first admin is made.

    python scripts/set_role.py --list
    python scripts/set_role.py someone@example.com Admin
    python scripts/set_role.py someone@example.com Visitor

In production:  fly ssh console -C "python scripts/set_role.py someone@example.com Admin"

The role is read from the database on every request, so the change applies at once;
the user does not need to sign in again.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.constants import Roles
from app.db.session import AsyncSessionLocal, engine
from app.models import User

ROLES = (Roles.VISITOR, Roles.ADMIN)


async def list_users() -> None:
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    for user in users:
        print(f"{user.id:>4}  {user.role:<8}  {user.email}")


async def set_role(email: str, role: str) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).filter(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email}. They must sign in once before getting a role.")
            return 1
        previous = user.role
        user.role = role
        await db.commit()
    print(f"{email}: {previous} -> {role}")
    return 0


async def main(argv: list[str]) -> int:
    try:
        if argv == ["--list"]:
            await list_users()
            return 0
        if len(argv) == 2 and argv[1] in ROLES:
            return await set_role(argv[0], argv[1])
    finally:
        await engine.dispose()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
