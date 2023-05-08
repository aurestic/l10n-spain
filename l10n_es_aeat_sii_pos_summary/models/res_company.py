from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sii_header_pos = fields.Char(
        string="POS SII Header",
        default="Ventas Contado",
    )
