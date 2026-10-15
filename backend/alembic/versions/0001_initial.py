"""Initial departments, users, recurring classes and availability."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False))
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("max_weekly_hours", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('student', 'supervisor')", name="valid_role"),
        sa.CheckConstraint("max_weekly_hours >= 0 AND max_weekly_hours <= 40", name="valid_hours"))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_department_id", "users", ["department_id"])
    for table, prefix in (("class_schedules", "class"), ("availability", "availability")):
        columns = [sa.Column("id", sa.Integer(), primary_key=True),
                   sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)]
        if table == "class_schedules":
            columns.append(sa.Column("course_name", sa.String(120), nullable=False))
        columns.extend([sa.Column("day_of_week", sa.Integer(), nullable=False),
                        sa.Column("start_time", sa.Time(), nullable=False),
                        sa.Column("end_time", sa.Time(), nullable=False),
                        sa.CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name=f"{prefix}_valid_day"),
                        sa.CheckConstraint("start_time < end_time", name=f"{prefix}_valid_times")])
        op.create_table(table, *columns)
        op.create_index(f"ix_{table}_student_id", table, ["student_id"])


def downgrade():
    op.drop_table("availability")
    op.drop_table("class_schedules")
    op.drop_table("users")
    op.drop_table("departments")
