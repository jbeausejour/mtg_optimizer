"""Consolidated migration

Revision ID: consolidated_migration
Revises: 
Create Date: 2024-08-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "consolidated_migration"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    # Create sets table
    op.create_table(
        "sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(10), unique=True, nullable=False),
        sa.Column("tcgplayer_id", sa.Integer()),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("uri", sa.String(255)),
        sa.Column("scryfall_uri", sa.String(255)),
        sa.Column("search_uri", sa.String(255)),
        sa.Column("released_at", sa.Date()),
        sa.Column("set_type", sa.String(50)),
        sa.Column("card_count", sa.Integer()),
        sa.Column("printed_size", sa.Integer()),
        sa.Column("digital", sa.Boolean(), default=False),
        sa.Column("nonfoil_only", sa.Boolean(), default=False),
        sa.Column("foil_only", sa.Boolean(), default=False),
        sa.Column("icon_svg_uri", sa.String(255)),
        sa.Column("last_updated", sa.DateTime()),
    )

    # Create site table
    op.create_table(
        "site",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("url", sa.String(255), unique=True, nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("country", sa.String(50), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
    )

    # Create marketplace_card table
    op.create_table(
        "marketplace_card",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("edition", sa.String(255), nullable=False),
        sa.Column("version", sa.String(255)),
        sa.Column("foil", sa.Boolean(), nullable=False, default=False),
        sa.Column("quality", sa.String(255), nullable=False),
        sa.Column("language", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column(
            "set_id", sa.String(36), sa.ForeignKey("sets.id", name="fk_card_set_id")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Create user_buylist_card table
    op.create_table(
        "user_buylist_card",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("edition", sa.String(255)),
        sa.Column("version", sa.String(255)),
        sa.Column("foil", sa.Boolean(), default=False),
        sa.Column("quality", sa.String(255), nullable=False),
        sa.Column("language", sa.String(255), nullable=False, default="English"),
        sa.Column("quantity", sa.Integer(), nullable=False, default=1),
    )

    # Create scryfall_card_data table
    op.create_table(
        "scryfall_card_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_name", sa.String(255), nullable=False),
        sa.Column("oracle_id", sa.String(255), nullable=False),
        sa.Column("multiverse_ids", sa.String(255)),
        sa.Column("reserved", sa.Boolean()),
        sa.Column("lang", sa.String(10)),
        sa.Column("set_code", sa.String(10)),
        sa.Column("set_name", sa.String(255)),
        sa.Column("collector_number", sa.String(20)),
        sa.Column("variation", sa.Boolean()),
        sa.Column("promo", sa.Boolean()),
        sa.Column("prices", sa.JSON()),
        sa.Column("purchase_uris", sa.JSON()),
        sa.Column("cardconduit_data", sa.JSON()),
        sa.Column("scan_timestamp", sa.DateTime()),
        sa.Column("purchase_data", sa.JSON()),
    )

    # Create scan table
    op.create_table(
        "scan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False
        ),  # Ensure this is not nullable
    )

    # Create scan_result table
    op.create_table(
        "scan_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scan_id",
            sa.Integer(),
            sa.ForeignKey("scan.id", name="fk_ScanResult_scan_id"),
            nullable=False,
        ),
        sa.Column(
            "marketplace_card_id",
            sa.Integer(),
            sa.ForeignKey(
                "marketplace_card.id", name="fk_ScanResult_marketplace_card_id"
            ),
            nullable=False,
        ),
        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey("site.id", name="fk_ScanResult_site_id"),
            nullable=False,
        ),
        sa.Column("price", sa.Float(), nullable=False),
    )

    # Create optimization_result table
    op.create_table(
        "optimization_result",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_names", sa.JSON()),
        sa.Column("results", sa.JSON()),
        sa.Column("timestamp", sa.DateTime()),
    )


def downgrade():
    op.drop_table("optimization_result")
    op.drop_table("scan_result")
    op.drop_table("scan")
    op.drop_table("scryfall_card_data")
    op.drop_table("user_buylist_card")
    op.drop_table("marketplace_card")
    op.drop_table("site")
    op.drop_table("sets")
