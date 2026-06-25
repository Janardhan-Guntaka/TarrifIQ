"""User profile mirror for auth.users."""

from uuid import UUID

from backend.db.connection import get_connection


class UserRepository:
    def upsert(self, user_id: UUID, email: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO public.users (id, email)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                (user_id, email),
            )
            conn.commit()
