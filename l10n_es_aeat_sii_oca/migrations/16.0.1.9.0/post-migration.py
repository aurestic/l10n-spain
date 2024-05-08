# Copyright 2024 Aures TIC - Jose Zambudio
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from openupgradelib import openupgrade

_rename_fields = [
    (
        "account.move",
        "account_move",
        "sii_state",
        "aeat_state",
    ),
    (
        "account.move",
        "account_move",
        "sii_header_sent",
        "aeat_header_sent",
    ),
    (
        "account.move",
        "account_move",
        "sii_send_error",
        "aeat_send_error",
    ),
    (
        "account.move",
        "account_move",
        "sii_send_failed",
        "aeat_send_failed",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    for model, table, oldfield, newfield in _rename_fields:
        if not openupgrade.column_exists(env.cr, table, oldfield):
            continue
        openupgrade.rename_fields(env, [(model, table, oldfield, newfield)])
