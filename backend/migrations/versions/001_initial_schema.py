"""Initial SmartLOTO schema

Revision ID: 001
Revises:
Create Date: 2026-06-10

Creates all tables, indexes, constraints, and critical DB-level safety rules:
1. Immutability trigger on procedure_versions.workflow_definition
2. Append-only rules on audit_events (no UPDATE, no DELETE)
3. Partial unique index for one active intervention per machine
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── machines ──────────────────────────────────────────────────────────────
    op.create_table(
        "machines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_id", sa.UUID(), nullable=True),
        sa.Column("internal_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("model_reference", sa.String(255), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("energy_types", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("location_in_site", sa.Text(), nullable=True),
        sa.Column("ar_spatial_reference", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "internal_code", name="uq_machine_code_per_site"),
    )
    op.create_index("idx_machines_site_id", "machines", ["site_id"])
    op.create_index("idx_machines_internal_code", "machines", ["internal_code"])
    op.create_index("idx_machines_is_active", "machines", ["is_active"])

    # ── machine_components ────────────────────────────────────────────────────
    op.create_table(
        "machine_components",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("energy_type", sa.String(30), nullable=False),
        sa.Column("physical_description", sa.Text(), nullable=True),
        sa.Column("location_hint", sa.Text(), nullable=True),
        sa.Column("default_vision_prompt", sa.Text(), nullable=True),
        sa.Column("ar_anchor_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_components_machine_active", "machine_components", ["machine_id", "is_active"])

    # ── procedures ────────────────────────────────────────────────────────────
    # Created WITHOUT active_version_id FK (circular reference resolved below)
    op.create_table(
        "procedures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("active_version_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_id", name="uq_procedure_per_machine"),
    )
    op.create_index("idx_procedures_machine_id", "procedures", ["machine_id"])

    # ── procedure_versions ────────────────────────────────────────────────────
    op.create_table(
        "procedure_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("procedure_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft_pending_review"),
        sa.Column("generation_source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("llm_model_used", sa.String(255), nullable=True),
        sa.Column("schema_version", sa.String(10), nullable=False, server_default="1.0"),
        sa.Column("workflow_definition", postgresql.JSONB(), nullable=False),
        sa.Column("validation_errors", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["procedure_id"], ["procedures.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("procedure_id", "version_number", name="uq_version_per_procedure"),
    )
    op.create_index("idx_procedure_versions_procedure_id", "procedure_versions", ["procedure_id"])
    op.create_index("idx_procedure_versions_status", "procedure_versions", ["status"])
    op.create_index("idx_procedure_versions_procedure_status", "procedure_versions", ["procedure_id", "status"])

    # Resolve circular FK: procedures.active_version_id → procedure_versions.id
    op.create_foreign_key(
        "fk_procedure_active_version",
        "procedures",
        "procedure_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── procedure_approvals ───────────────────────────────────────────────────
    op.create_table(
        "procedure_approvals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["version_id"], ["procedure_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_approvals_version_id", "procedure_approvals", ["version_id"])

    # ── interventions ─────────────────────────────────────────────────────────
    op.create_table(
        "interventions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("procedure_version_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("operator_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("current_step_ref", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aborted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abort_reason", sa.Text(), nullable=True),
        sa.Column("pdf_report_url", sa.Text(), nullable=True),
        sa.Column("operator_signature_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["procedure_version_id"], ["procedure_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_interventions_machine_id", "interventions", ["machine_id"])
    op.create_index("idx_interventions_operator", "interventions", ["operator_name"])
    op.create_index("idx_interventions_status", "interventions", ["status"])

    # Partial unique index: only one active intervention per machine
    op.execute(
        """
        CREATE UNIQUE INDEX uq_one_active_intervention_per_machine
        ON interventions (machine_id)
        WHERE status IN ('pending', 'in_progress', 'paused')
        """
    )

    # ── intervention_steps ────────────────────────────────────────────────────
    op.create_table(
        "intervention_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("intervention_id", sa.UUID(), nullable=False),
        sa.Column("step_ref", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("validation_method_used", sa.String(20), nullable=True),
        sa.Column("ai_confidence_score", sa.Float(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_step_per_intervention
        ON intervention_steps (intervention_id, step_ref)
        """
    )
    op.create_index("idx_steps_intervention_id", "intervention_steps", ["intervention_id"])
    op.create_index("idx_steps_status", "intervention_steps", ["status"])

    # ── audit_events ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("machine_id", sa.UUID(), nullable=True),
        sa.Column("intervention_id", sa.UUID(), nullable=True),
        sa.Column("procedure_version_id", sa.UUID(), nullable=True),
        sa.Column("step_ref", sa.String(255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["procedure_version_id"], ["procedure_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_machine", "audit_events", ["machine_id", "occurred_at"])
    op.create_index("idx_audit_intervention", "audit_events", ["intervention_id", "occurred_at"])
    op.create_index("idx_audit_event_type", "audit_events", ["event_type", "occurred_at"])
    op.create_index("idx_audit_procedure_version", "audit_events", ["procedure_version_id"])
    op.create_index("idx_audit_occurred_at", "audit_events", ["occurred_at"])

    # ── Safety DB rules ───────────────────────────────────────────────────────

    # 1. Immutability of approved procedure versions
    # Any attempt to UPDATE workflow_definition on an approved/published/archived
    # version raises a PostgreSQL exception at the DB level (double protection
    # alongside the application-level check in ProcedureService).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_approved_workflow_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IN ('approved', 'published', 'archived')
               AND NEW.workflow_definition IS DISTINCT FROM OLD.workflow_definition THEN
                RAISE EXCEPTION
                    'IMMUTABILITY_VIOLATION: workflow_definition cannot be modified once '
                    'procedure version status is %. Create a new draft version. '
                    'Version ID: %',
                    OLD.status, OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_immutable_approved_procedure
        BEFORE UPDATE ON procedure_versions
        FOR EACH ROW
        EXECUTE FUNCTION prevent_approved_workflow_modification();
        """
    )

    # 2. Audit trail append-only enforcement
    # These RULE objects silently discard UPDATE and DELETE attempts from any role.
    # A more paranoid setup would use a dedicated read-only role and deny all but INSERT.
    op.execute(
        "CREATE RULE no_update_audit_events AS ON UPDATE TO audit_events DO INSTEAD NOTHING;"
    )
    op.execute(
        "CREATE RULE no_delete_audit_events AS ON DELETE TO audit_events DO INSTEAD NOTHING;"
    )

    # 3. updated_at auto-refresh trigger (applied to all mutable tables)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("machines", "machine_components", "procedures", "procedure_versions", "interventions"):
        op.execute(
            f"""
            CREATE TRIGGER trg_refresh_updated_at_{table}
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION refresh_updated_at();
            """
        )


def downgrade() -> None:
    # Drop triggers and rules first
    for table in ("machines", "machine_components", "procedures", "procedure_versions", "interventions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_refresh_updated_at_{table} ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_immutable_approved_procedure ON procedure_versions;")
    op.execute("DROP FUNCTION IF EXISTS prevent_approved_workflow_modification();")
    op.execute("DROP FUNCTION IF EXISTS refresh_updated_at();")
    op.execute("DROP RULE IF EXISTS no_update_audit_events ON audit_events;")
    op.execute("DROP RULE IF EXISTS no_delete_audit_events ON audit_events;")

    # Drop tables in reverse dependency order
    op.execute("DROP INDEX IF EXISTS uq_step_per_intervention;")
    op.execute("DROP INDEX IF EXISTS uq_one_active_intervention_per_machine;")
    op.drop_constraint("fk_procedure_active_version", "procedures", type_="foreignkey")

    for table in (
        "audit_events",
        "intervention_steps",
        "interventions",
        "procedure_approvals",
        "procedure_versions",
        "procedures",
        "machine_components",
        "machines",
    ):
        op.drop_table(table)
