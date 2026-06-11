"""Initial SmartLOTO authoring schema

Revision ID: 001
Revises:
Create Date: 2026-06-10

Creates all tables in the 'authoring' PostgreSQL schema (avoids conflicts
with the field-service 'public.procedures' and 'public.interventions' tables).
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

SCHEMA = "authoring"


def upgrade() -> None:
    # Create the authoring schema
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

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
        schema=SCHEMA,
    )
    op.create_index("idx_machines_site_id", "machines", ["site_id"], schema=SCHEMA)
    op.create_index("idx_machines_internal_code", "machines", ["internal_code"], schema=SCHEMA)
    op.create_index("idx_machines_is_active", "machines", ["is_active"], schema=SCHEMA)

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
        sa.ForeignKeyConstraint(["machine_id"], [f"{SCHEMA}.machines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("idx_components_machine_active", "machine_components", ["machine_id", "is_active"], schema=SCHEMA)

    # ── procedures ────────────────────────────────────────────────────────────
    op.create_table(
        "procedures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("active_version_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], [f"{SCHEMA}.machines.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_id", name="uq_procedure_per_machine"),
        schema=SCHEMA,
    )
    op.create_index("idx_procedures_machine_id", "procedures", ["machine_id"], schema=SCHEMA)

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
        sa.ForeignKeyConstraint(["procedure_id"], [f"{SCHEMA}.procedures.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("procedure_id", "version_number", name="uq_version_per_procedure"),
        schema=SCHEMA,
    )
    op.create_index("idx_procedure_versions_procedure_id", "procedure_versions", ["procedure_id"], schema=SCHEMA)
    op.create_index("idx_procedure_versions_status", "procedure_versions", ["status"], schema=SCHEMA)
    op.create_index("idx_procedure_versions_procedure_status", "procedure_versions", ["procedure_id", "status"], schema=SCHEMA)

    # Resolve circular FK: procedures.active_version_id → procedure_versions.id
    op.create_foreign_key(
        "fk_procedure_active_version",
        "procedures",
        "procedure_versions",
        ["active_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
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
        sa.ForeignKeyConstraint(["version_id"], [f"{SCHEMA}.procedure_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("idx_approvals_version_id", "procedure_approvals", ["version_id"], schema=SCHEMA)

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
        sa.ForeignKeyConstraint(["machine_id"], [f"{SCHEMA}.machines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["procedure_version_id"], [f"{SCHEMA}.procedure_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("idx_interventions_machine_id", "interventions", ["machine_id"], schema=SCHEMA)
    op.create_index("idx_interventions_operator", "interventions", ["operator_name"], schema=SCHEMA)
    op.create_index("idx_interventions_status", "interventions", ["status"], schema=SCHEMA)

    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_one_active_intervention_per_machine
        ON {SCHEMA}.interventions (machine_id)
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
        sa.ForeignKeyConstraint(["intervention_id"], [f"{SCHEMA}.interventions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_step_per_intervention
        ON {SCHEMA}.intervention_steps (intervention_id, step_ref)
        """
    )
    op.create_index("idx_steps_intervention_id", "intervention_steps", ["intervention_id"], schema=SCHEMA)
    op.create_index("idx_steps_status", "intervention_steps", ["status"], schema=SCHEMA)

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
        sa.ForeignKeyConstraint(["machine_id"], [f"{SCHEMA}.machines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["intervention_id"], [f"{SCHEMA}.interventions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["procedure_version_id"], [f"{SCHEMA}.procedure_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("idx_audit_machine", "audit_events", ["machine_id", "occurred_at"], schema=SCHEMA)
    op.create_index("idx_audit_intervention", "audit_events", ["intervention_id", "occurred_at"], schema=SCHEMA)
    op.create_index("idx_audit_event_type", "audit_events", ["event_type", "occurred_at"], schema=SCHEMA)
    op.create_index("idx_audit_procedure_version", "audit_events", ["procedure_version_id"], schema=SCHEMA)
    op.create_index("idx_audit_occurred_at", "audit_events", ["occurred_at"], schema=SCHEMA)

    # ── Safety DB rules ───────────────────────────────────────────────────────

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.prevent_approved_workflow_modification()
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
        f"""
        CREATE TRIGGER trg_immutable_approved_procedure
        BEFORE UPDATE ON {SCHEMA}.procedure_versions
        FOR EACH ROW
        EXECUTE FUNCTION {SCHEMA}.prevent_approved_workflow_modification();
        """
    )

    op.execute(
        f"CREATE RULE no_update_audit_events AS ON UPDATE TO {SCHEMA}.audit_events DO INSTEAD NOTHING;"
    )
    op.execute(
        f"CREATE RULE no_delete_audit_events AS ON DELETE TO {SCHEMA}.audit_events DO INSTEAD NOTHING;"
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.refresh_updated_at()
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
            BEFORE UPDATE ON {SCHEMA}.{table}
            FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.refresh_updated_at();
            """
        )


def downgrade() -> None:
    for table in ("machines", "machine_components", "procedures", "procedure_versions", "interventions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_refresh_updated_at_{table} ON {SCHEMA}.{table};")

    op.execute(f"DROP TRIGGER IF EXISTS trg_immutable_approved_procedure ON {SCHEMA}.procedure_versions;")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.prevent_approved_workflow_modification();")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.refresh_updated_at();")
    op.execute(f"DROP RULE IF EXISTS no_update_audit_events ON {SCHEMA}.audit_events;")
    op.execute(f"DROP RULE IF EXISTS no_delete_audit_events ON {SCHEMA}.audit_events;")

    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.uq_step_per_intervention;")
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.uq_one_active_intervention_per_machine;")
    op.drop_constraint("fk_procedure_active_version", "procedures", type_="foreignkey", schema=SCHEMA)

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
        op.drop_table(table, schema=SCHEMA)

    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;")
