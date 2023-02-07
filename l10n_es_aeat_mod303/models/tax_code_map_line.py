# -*- coding: utf-8 -*-
from openerp import fields, models


class AeatModMapTaxCodeLine(models.Model):
    _inherit = 'aeat.mod.map.tax.code.line'

    # quitamos el required
    tax_codes = fields.Many2many(
        comodel_name='account.tax.code.template',
        required=False)