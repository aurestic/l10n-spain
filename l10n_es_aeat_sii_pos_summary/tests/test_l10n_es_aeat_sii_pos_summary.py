from odoo import fields
from odoo.tests import common, tagged


@tagged("-at_install", "post_install")
class TestSiiPosSummary(common.TransactionCase):
    def setUp(self):
        super(TestSiiPosSummary, self).setUp()
        # I click on create a new session button
        self.pos_config = self.env.ref("point_of_sale.pos_config_main")
        self.pos_config.cash_control = False
        self.cash_journal = self.env["account.journal"].search(
            [("company_id", "=", self.env.company.id), ("type", "=", "cash")], limit=1
        )
        self.currency_pricelist = self.env["product.pricelist"].create(
            {
                "name": "Public Pricelist",
                "currency_id": self.env.company.currency_id.id,
            }
        )
        self.pos_config.available_pricelist_ids = [(6, 0, self.currency_pricelist.ids)]
        self.pos_config.pricelist_id = self.currency_pricelist
        self.pos_receivable_account = (
            self.env.company.account_default_pos_receivable_account_id
        )
        self.cash_payment_method = self.env["pos.payment.method"].create(
            {
                "name": "Cash",
                "receivable_account_id": self.pos_receivable_account.id,
                "is_cash_count": True,
                "cash_journal_id": self.cash_journal.id,
                "company_id": self.env.company.id,
            }
        )
        self.pos_config.write(
            {"payment_method_ids": [(4, self.cash_payment_method.id)]}
        )

        self.pos_config.open_session_cb(check_coa=False)

        self.current_session = self.pos_config.current_session_id

        self.product1 = self.env["product.product"].create(
            {
                "name": "Product1",
                "available_in_pos": True,
                "list_price": 0.90,
            }
        )
        pos_order1_vals = {
            "data": {
                "amount_paid": self.product1.list_price,
                "amount_return": 0,
                "amount_tax": self.product1.list_price,
                "amount_total": self.product1.list_price,
                "creation_date": fields.Datetime.to_string(fields.Datetime.now()),
                "fiscal_position_id": False,
                "pricelist_id": self.pos_config.available_pricelist_ids[0].id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "discount": 0,
                            "id": 42,
                            "pack_lot_ids": [],
                            "price_unit": 0.9,
                            "product_id": self.product1.id,
                            "price_subtotal": 0.9,
                            "price_subtotal_incl": 0.9,
                            "qty": 1,
                            "tax_ids": [(6, 0, [])],
                        },
                    ]
                ],
                "name": "Order 00042-003-0014",
                "partner_id": False,
                "pos_session_id": self.current_session.id,
                "sequence_number": 2,
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "amount": 0.9,
                            "name": fields.Datetime.now(),
                            "payment_method_id": self.cash_payment_method.id,
                        },
                    ]
                ],
                "uid": "00042-003-0014",
                "user_id": self.env.uid,
            },
            "id": "00042-003-0014",
            "to_invoice": False,
            "is_l10n_es_simplified_invoice": True,
        }

        pos_order2_vals = {
            "data": {
                "amount_paid": self.product1.list_price,
                "amount_return": 0,
                "amount_tax": self.product1.list_price,
                "amount_total": self.product1.list_price,
                "creation_date": fields.Datetime.to_string(fields.Datetime.now()),
                "fiscal_position_id": False,
                "pricelist_id": self.pos_config.available_pricelist_ids[0].id,
                "lines": [
                    [
                        0,
                        0,
                        {
                            "discount": 0,
                            "id": 43,
                            "pack_lot_ids": [],
                            "price_unit": 0.9,
                            "product_id": self.product1.id,
                            "price_subtotal": 0.9,
                            "price_subtotal_incl": 0.9,
                            "qty": 1,
                            "tax_ids": [(6, 0, [])],
                        },
                    ]
                ],
                "name": "Order 00042-003-0015",
                "partner_id": False,
                "pos_session_id": self.current_session.id,
                "sequence_number": 2,
                "statement_ids": [
                    [
                        0,
                        0,
                        {
                            "amount": 0.9,
                            "name": fields.Datetime.now(),
                            "payment_method_id": self.cash_payment_method.id,
                        },
                    ]
                ],
                "uid": "00042-003-0015",
                "user_id": self.env.uid,
            },
            "id": "00042-003-0015",
            "to_invoice": False,
            "is_l10n_es_simplified_invoice": True,
        }

        self.env["pos.order"].create_from_ui([pos_order1_vals, pos_order2_vals])

    def test_01_check_create_queue_job_sii(self):
        company = self.current_session.company_id
        company.write(
            {
                "sii_enabled": True,
                "sii_test": True,
                "use_connector": True,
                "vat": "ESU2687761C",
                "sii_description_method": "manual",
                "tax_agency_id": self.env.ref("l10n_es_aeat.aeat_tax_agency_spain"),
            }
        )
        self.current_session.action_pos_session_closing_control()
        self.assertEqual(self.current_session.state, "closed")
        self.assertTrue(self.current_session.move_id)
        self.assertTrue(self.current_session.simplified_jobs_ids)
