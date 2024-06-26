# -*- coding: utf-8 -*-

__name__ = ("Migrando tipos de cuenta")


account_types_mapping = [
    ('l10n_es.capital', 'l10n_es.account_type_capital'),
    ('l10n_es.financieras', 'l10n_es.account_type_financieras'),
    ('l10n_es.gastos', 'account.data_account_type_expense'),
    ('l10n_es.gastos_neto', 'l10n_es.account_type_gastos_neto'),
    ('l10n_es.ingresos', 'account.data_account_type_income'),
    ('l10n_es.ingresos_neto', 'l10n_es.account_type_ingresos_neto'),
    ('l10n_es.inmo', 'l10n_es.account_type_inmo'),
    ('l10n_es.stock', 'l10n_es.account_type_stock'),
    ('l10n_es.tax', 'account.conf_account_type_tax'),
    ('l10n_es.terceros', 'l10n_es.account_type_terceros'),
    ('l10n_es.terceros_-_pay', 'account.data_account_type_payable'),
    ('l10n_es.terceros_-_rec', 'account.data_account_type_receivable'),
    ('l10n_es.view', 'account.data_account_type_view'),
]


def map_account_types(cr):
    for old_value, new_value in account_types_mapping:
        old_module, old_name = old_value.split('.')
        new_module, new_name = new_value.split('.')
        cr.execute("SELECT res_id "
                   "FROM ir_model_data "
                   "WHERE module=%s AND name=%s "
                   "LIMIT 1", (old_module, old_name))
        old_id = cr.fetchone()[0]
        cr.execute("SELECT res_id "
                   "FROM ir_model_data "
                   "WHERE module=%s AND name=%s "
                   "LIMIT 1", (new_module, new_name))
        new_id = cr.fetchone()[0]
        cr.execute("UPDATE account_account "
                   "SET user_type=%s "
                   "WHERE user_type=%s", (new_id, old_id))


def migrate(cr, version):
    if not version:
        return
    map_account_types(cr)
