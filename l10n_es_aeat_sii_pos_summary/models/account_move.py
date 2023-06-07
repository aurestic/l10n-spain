from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_aeat_tax_info(self):
        self.ensure_one()
        res = super(AccountMove, self)._get_aeat_tax_info()
        if self._context.get("from_pos"):
            pos_orders = self._context.get("pos_orders")
            res = {}
            for line in self.line_ids:
                sign = -1 if sum(pos_orders.mapped("amount_total")) >= 0.0 else 1
                for tax in line.tax_ids:
                    line._process_aeat_tax_base_info(res, tax, sign)
                if line.tax_line_id:
                    tax = line.tax_line_id
                    if line.credit:
                        repartition_lines = tax.invoice_repartition_line_ids
                    else:
                        repartition_lines = tax.refund_repartition_line_ids
                    if (
                        len(repartition_lines) > 2
                        and line.tax_repartition_line_id.factor_percent < 0
                    ):
                        continue
                    line._process_aeat_tax_fee_info(res, tax, sign)
        return res

    def _is_sii_type_breakdown_required(self, taxes_dict):
        self.ensure_one()
        if self._context.get("from_pos"):
            return False
        return super(AccountMove, self)._is_sii_type_breakdown_required(taxes_dict)

    @api.model
    def _get_sii_tax_dict(self, tax_line, tax_lines):
        self.ensure_one()
        tax_dict = super(AccountMove, self)._get_sii_tax_dict(tax_line, tax_lines)
        if self._context.get("from_pos"):
            tax_dict["CuotaRepercutida"] = round(tax_dict.pop("CuotaSoportada"), 2)
        return tax_dict
