"""Initial schema for all 16 DropSafe core tables.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-10-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
uuid_type = sa.Uuid(as_uuid=True).with_variant(postgresql.UUID(as_uuid=True), "postgresql")


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled', 'pending')", name="ck_users_status"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, nullable=False),
        sa.Column("role", sa.String(length=30), primary_key=True, nullable=False),
        sa.Column("assigned_by", uuid_type, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin', 'auditor')", name="ck_user_roles_role"),
    )
    op.create_index("ix_user_roles_role_user_id", "user_roles", ["role", "user_id"])

    # 3. user_keys
    op.create_table(
        "user_keys",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("key_purpose", sa.String(length=20), nullable=False),
        sa.Column("algorithm", sa.String(length=40), nullable=False),
        sa.Column("public_key_jwk", json_type, nullable=False),
        sa.Column("public_key_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("key_purpose IN ('encryption', 'signing')", name="ck_user_keys_key_purpose"),
        sa.CheckConstraint("key_version > 0", name="ck_user_keys_key_version"),
        sa.CheckConstraint("status IN ('active', 'retired', 'revoked')", name="ck_user_keys_status"),
        sa.UniqueConstraint("user_id", "key_purpose", "key_version", name="uq_user_keys_user_purpose_version"),
    )
    op.create_index("ix_user_keys_fingerprint", "user_keys", ["public_key_fingerprint"])
    op.create_index("ix_user_keys_user_purpose_status", "user_keys", ["user_id", "key_purpose", "status"])

    # 4. attribute_definitions
    op.create_table(
        "attribute_definitions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("allowed_values", json_type, nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("value_type IN ('string', 'boolean', 'integer', 'string_set')", name="ck_attribute_definitions_value_type"),
        sa.UniqueConstraint("name", name="uq_attribute_definitions_name"),
    )
    op.create_index("ix_attribute_definitions_is_active_name", "attribute_definitions", ["is_active", "name"])

    # 5. user_attributes
    op.create_table(
        "user_attributes",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attribute_definition_id", uuid_type, sa.ForeignKey("attribute_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("value", json_type, nullable=False),
        sa.Column("assigned_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(length=30), server_default="admin", nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_user_attributes_validity_window"),
        sa.UniqueConstraint("user_id", "attribute_definition_id", name="uq_user_attributes_user_attr_def"),
    )
    op.create_index("ix_user_attributes_user_attr_def", "user_attributes", ["user_id", "attribute_definition_id"])
    op.create_index("ix_user_attributes_attr_valid_until", "user_attributes", ["attribute_definition_id", "valid_until"])

    # 6. attribute_credential_signatures
    op.create_table(
        "attribute_credential_signatures",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("payload_hash", sa.LargeBinary(), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.Column("issuer_key_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("credential_version > 0", name="ck_attr_cred_sigs_version"),
        sa.CheckConstraint("status IN ('active', 'superseded', 'revoked')", name="ck_attr_cred_sigs_status"),
        sa.UniqueConstraint("user_id", "credential_version", name="uq_attr_cred_sigs_user_version"),
    )
    op.create_index("ix_attr_cred_sigs_issuer_key_id", "attribute_credential_signatures", ["issuer_key_id"])
    op.create_index("ix_attr_cred_sigs_user_status_version", "attribute_credential_signatures", ["user_id", "status", "credential_version"])

    # 7. documents (created first without the circular foreign key to document_versions)
    op.create_table(
        "documents",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("owner_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=150), nullable=True),
        sa.Column("current_version_id", uuid_type, nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'deleted', 'quarantined')", name="ck_documents_status"),
    )
    op.create_index("ix_documents_owner_status_updated", "documents", ["owner_id", "status", "updated_at"])
    op.create_index("ix_documents_owner_created", "documents", ["owner_id", "created_at"])

    # 8. document_versions
    op.create_table(
        "document_versions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("ciphertext_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ciphertext_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("manifest", json_type, nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=True),
        sa.Column("signature_algorithm", sa.String(length=40), nullable=True),
        sa.Column("signing_key_id", uuid_type, sa.ForeignKey("user_keys.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("commitment_version", sa.String(length=30), server_default="v1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number > 0", name="ck_document_versions_version_number"),
        sa.CheckConstraint("key_version > 0", name="ck_document_versions_key_version"),
        sa.CheckConstraint("ciphertext_size_bytes >= 0", name="ck_document_versions_ciphertext_size"),
        sa.CheckConstraint("status IN ('pending', 'finalized', 'retired', 'failed')", name="ck_document_versions_status"),
        sa.CheckConstraint(
            "(signature IS NULL AND signature_algorithm IS NULL) OR "
            "(signature IS NOT NULL AND signature_algorithm IS NOT NULL)",
            name="ck_document_versions_signature_parity",
        ),
        sa.UniqueConstraint("object_key", name="uq_document_versions_object_key"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_doc_version"),
    )
    op.create_index("ix_document_versions_doc_version", "document_versions", ["document_id", "version_number"])

    # Now add circular FK from documents.current_version_id -> document_versions.id
    with op.batch_alter_table("documents") as batch_op:
        batch_op.create_foreign_key(
            "fk_documents_current_version_id",
            "document_versions",
            ["current_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # 9. document_key_envelopes
    op.create_table(
        "document_key_envelopes",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_version_id", uuid_type, sa.ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_encryption_key_id", uuid_type, sa.ForeignKey("user_keys.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("wrapping_algorithm", sa.String(length=40), server_default="RSA-OAEP-3072", nullable=False),
        sa.Column("wrapped_key", sa.LargeBinary(), nullable=False),
        sa.Column("envelope_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("envelope_version > 0", name="ck_doc_key_envelopes_version"),
        sa.CheckConstraint("status IN ('active', 'revoked', 'superseded')", name="ck_doc_key_envelopes_status"),
        sa.UniqueConstraint(
            "document_version_id",
            "recipient_user_id",
            "recipient_encryption_key_id",
            "envelope_version",
            name="uq_doc_key_envelopes_unique_recipient_env",
        ),
    )
    op.create_index("ix_doc_key_envelopes_recipient_status_created", "document_key_envelopes", ["recipient_user_id", "status", "created_at"])
    op.create_index("ix_doc_key_envelopes_version_status", "document_key_envelopes", ["document_version_id", "status"])

    # 10. access_policies
    op.create_table(
        "access_policies",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("policy_schema_version", sa.String(length=30), server_default="v1", nullable=False),
        sa.Column("policy_ast", json_type, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number > 0", name="ck_access_policies_version_number"),
        sa.CheckConstraint("status IN ('draft', 'active', 'superseded', 'disabled')", name="ck_access_policies_status"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_access_policies_doc_version"),
    )
    op.create_index("ix_access_policies_doc_status_version", "access_policies", ["document_id", "status", "version_number"])

    # 11. access_grants
    op.create_table(
        "access_grants",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grantor_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grantee_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("grant_type", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("permissions", json_type, nullable=False),
        sa.Column("policy_version_id", uuid_type, sa.ForeignKey("access_policies.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=300), nullable=True),
        sa.CheckConstraint("grant_type IN ('user', 'link')", name="ck_access_grants_grant_type"),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_access_grants_status"),
        sa.CheckConstraint(
            "(grant_type = 'user' AND grantee_user_id IS NOT NULL) OR "
            "(grant_type = 'link' AND grantee_user_id IS NULL)",
            name="ck_access_grants_grantee_parity",
        ),
    )
    op.create_index("ix_access_grants_doc_status", "access_grants", ["document_id", "status"])
    op.create_index("ix_access_grants_grantee_status_created", "access_grants", ["grantee_user_id", "status", "created_at"])
    op.create_index("ix_access_grants_expires_at", "access_grants", ["expires_at"])

    # 12. share_links
    op.create_table(
        "share_links",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("access_grant_id", uuid_type, sa.ForeignKey("access_grants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("token_key_version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_share_links_status"),
        sa.CheckConstraint("max_uses IS NULL OR max_uses > 0", name="ck_share_links_max_uses"),
        sa.CheckConstraint("use_count >= 0", name="ck_share_links_use_count"),
        sa.UniqueConstraint("token_hash", name="uq_share_links_token_hash"),
    )
    op.create_index("ix_share_links_access_grant_id", "share_links", ["access_grant_id"])
    op.create_index("ix_share_links_status_expires", "share_links", ["status", "expires_at"])

    # 13. audit_batches
    op.create_table(
        "audit_batches",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("batch_number", sa.BigInteger(), nullable=False),
        sa.Column("first_sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("last_sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("merkle_root", sa.LargeBinary(), nullable=False),
        sa.Column("tree_algorithm", sa.String(length=40), server_default="SHA-256-MERKLE-v1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="prepared", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("batch_number > 0", name="ck_audit_batches_batch_number"),
        sa.CheckConstraint("event_count > 0", name="ck_audit_batches_event_count"),
        sa.CheckConstraint("status IN ('prepared', 'anchoring', 'anchored', 'failed', 'superseded')", name="ck_audit_batches_status"),
        sa.CheckConstraint("last_sequence_number >= first_sequence_number", name="ck_audit_batches_sequence_order"),
        sa.UniqueConstraint("batch_number", name="uq_audit_batches_batch_number"),
    )
    op.create_index("ix_audit_batches_status_created", "audit_batches", ["status", "created_at"])
    op.create_index("ix_audit_batches_first_last_seq", "audit_batches", ["first_sequence_number", "last_sequence_number"])

    # 14. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("source_ip_hash", sa.LargeBinary(), nullable=True),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column("previous_event_hash", sa.LargeBinary(), nullable=True),
        sa.Column("event_hash", sa.LargeBinary(), nullable=False),
        sa.Column("batch_id", uuid_type, sa.ForeignKey("audit_batches.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("outcome IN ('success', 'denied', 'failure', 'pending')", name="ck_audit_events_outcome"),
        sa.UniqueConstraint("sequence_number", name="uq_audit_events_sequence_number"),
        sa.UniqueConstraint("event_hash", name="uq_audit_events_event_hash"),
    )
    op.create_index("ix_audit_events_sequence_number", "audit_events", ["sequence_number"], unique=True)
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_actor_occurred", "audit_events", ["actor_user_id", "occurred_at"])
    op.create_index("ix_audit_events_doc_occurred", "audit_events", ["document_id", "occurred_at"])
    op.create_index("ix_audit_events_type_occurred", "audit_events", ["event_type", "occurred_at"])
    op.create_index("ix_audit_events_batch_id", "audit_events", ["batch_id"])

    # 15. blockchain_anchors
    op.create_table(
        "blockchain_anchors",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("batch_id", uuid_type, sa.ForeignKey("audit_batches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chain_id", sa.BigInteger(), nullable=False),
        sa.Column("network_name", sa.String(length=50), nullable=False),
        sa.Column("contract_address", sa.String(length=100), nullable=False),
        sa.Column("transaction_hash", sa.String(length=100), nullable=True),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'submitted', 'confirmed', 'failed', 'reorged')", name="ck_blockchain_anchors_status"),
        sa.CheckConstraint("confirmation_count >= 0", name="ck_blockchain_anchors_confirmation_count"),
    )
    op.create_index("ix_blockchain_anchors_transaction_hash", "blockchain_anchors", ["transaction_hash"])
    op.create_index("ix_blockchain_anchors_status_created", "blockchain_anchors", ["status", "created_at"])
    op.create_index("ix_blockchain_anchors_batch_created", "blockchain_anchors", ["batch_id", "created_at"])

    # 16. outbox_jobs
    op.create_table(
        "outbox_jobs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("job_type IN ('build_audit_batch', 'anchor_batch')", name="ck_outbox_jobs_job_type"),
        sa.CheckConstraint("status IN ('pending', 'processing', 'succeeded', 'failed', 'dead_letter')", name="ck_outbox_jobs_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_jobs_attempt_count"),
    )
    op.create_index("ix_outbox_jobs_status_run_after", "outbox_jobs", ["status", "run_after"])
    op.create_index("ix_outbox_jobs_type_aggregate", "outbox_jobs", ["job_type", "aggregate_id"])
    op.create_index("ix_outbox_jobs_locked_at", "outbox_jobs", ["locked_at"])


def downgrade() -> None:
    # 1. Drop circular FK first
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_current_version_id", type_="foreignkey")

    # 2. Drop tables in reverse dependency order
    op.drop_table("outbox_jobs")
    op.drop_table("blockchain_anchors")
    op.drop_table("audit_events")
    op.drop_table("audit_batches")
    op.drop_table("share_links")
    op.drop_table("access_grants")
    op.drop_table("access_policies")
    op.drop_table("document_key_envelopes")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("attribute_credential_signatures")
    op.drop_table("user_attributes")
    op.drop_table("attribute_definitions")
    op.drop_table("user_keys")
    op.drop_table("user_roles")
    op.drop_table("users")
