import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

SII_STATES = [
    ("not_sent", "Not sent"),
    ("sent", "Sent"),
    ("sent_w_errors", "Accepted with errors"),
    (
        "sent_modified",
        "Registered in SII but last modifications not sent",
    ),
    ("cancelled", "Cancelled"),
    ("cancelled_modified", "Cancelled in SII but last modifications not sent"),
]


class PosSession(models.Model):
    _inherit = "pos.session"

    sii_description = fields.Text(
        string="SII description",
        compute="_compute_sii_description",
        default="/",
        store=True,
        copy=False,
        readonly=False,
    )
    sii_state = fields.Selection(
        selection=SII_STATES,
        string="SII send state",
        default="not_sent",
        copy=False,
        readonly=True,
    )
    sii_csv = fields.Char(string="SII CSV", copy=False, readonly=True)
    sii_return = fields.Text(string="SII Return", copy=False, readonly=True)
    sii_header_sent = fields.Text(
        string="SII last header sent",
        copy=False,
        readonly=True,
    )
    sii_content_sent = fields.Text(
        string="SII last content sent",
        copy=False,
        readonly=True,
    )
    sii_send_error = fields.Text(
        string="SII Send Error",
        copy=False,
        readonly=True,
    )
    sii_send_failed = fields.Boolean(
        string="SII send failed",
        copy=False,
        readonly=True,
    )
    simplified_jobs_ids = fields.Many2many(
        comodel_name="queue.job",
        column1="pos_session_id",
        column2="job_id",
        string="Connector Jobs",
        copy=False,
    )
    sii_enabled = fields.Boolean(
        "SII Enabled",
        default=True,
    )

    def _compute_sii_description(self):
        return self.company_id.sii_header_pos or "/"

    def send_sii(self):
        queue_obj = self.env["queue.job"]
        for session in self:
            company = session.company_id
            if not company.use_connector:
                session._process_send_summary_to_sii()
            else:
                eta = company._get_sii_eta()
                new_delay = (
                    session.sudo()
                    .with_context(company_id=company.id)
                    .with_delay(eta=eta if not session.sii_send_failed else False)
                    .send_one_session()
                )
                job = queue_obj.search([("uuid", "=", new_delay.uuid)], limit=1)
                session.sudo().simplified_jobs_ids |= job

    def send_sii_modification(self):
        queue_obj = self.env["queue.job"]
        for session in self:
            company = session.company_id
            if not company.use_connector:
                session._process_send_summary_to_sii(modification=True)
            else:
                eta = company._get_sii_eta()
                new_delay = (
                    session.sudo()
                    .with_context(company_id=company.id)
                    .with_delay(eta=eta if not session.sii_send_failed else False)
                    .send_one_session_modification()
                )
                job = queue_obj.search([("uuid", "=", new_delay.uuid)], limit=1)
                session.sudo().session_sii_jobs_ids |= job

    def _other_checks_before_send(self):
        self.ensure_one()
        if not self.config_id.l10n_es_simplified_invoice_sequence_id:
            raise UserError(_("A simplified invoice sequence must be cofigured"))

    def _process_send_summary_to_sii(self, modification=False):
        for session in self:
            if not session.sii_enabled or not session.company_id.sii_enabled:
                continue
            if session.sii_state not in ("sent", "not_sent"):
                continue
            session._other_checks_before_send()
            tipo_comunicacion = "A0"
            if modification:
                tipo_comunicacion = "A1"
            header = session.move_id._get_sii_header(tipo_comunicacion)
            summary_vals = {
                "sii_header_sent": json.dumps(header, indent=4),
            }
            try:
                summary_dict = session._get_sii_summary_dict()
                summary_vals["sii_content_sent"] = json.dumps(summary_dict, indent=4)
                serv = session.move_id._connect_sii("out_invoice")
                res = serv.SuministroLRFacturasEmitidas(header, summary_dict)
                res_line = res["RespuestaLinea"][0]
                if res["EstadoEnvio"] == "Correcto":
                    summary_vals.update(
                        {
                            "sii_state": "sent",
                            "sii_csv": res["CSV"],
                            "sii_send_failed": False,
                        }
                    )
                elif (
                    res["EstadoEnvio"] == "ParcialmenteCorrecto"
                    and res_line["EstadoRegistro"] == "AceptadoConErrores"
                ):
                    summary_vals.update(
                        {
                            "sii_state": "sent_w_errors",
                            "sii_csv": res["CSV"],
                            "sii_send_failed": True,
                        }
                    )
                else:
                    summary_vals["sii_send_failed"] = True
                summary_vals["sii_return"] = res
                send_error = False
                if res_line["CodigoErrorRegistro"]:
                    send_error = "{} | {}".format(
                        str(res_line["CodigoErrorRegistro"]),
                        str(res_line["DescripcionErrorRegistro"])[:60],
                    )
                summary_vals["sii_send_error"] = send_error
                session.write(summary_vals)
            except Exception as fault:
                new_cr = Registry(self.env.cr.dbname).cursor()
                env = api.Environment(new_cr, self.env.uid, self.env.context)
                session = env["pos.session"].browse(self.id)
                summary_vals.update(
                    {
                        "sii_send_failed": True,
                        "sii_send_error": repr(fault)[:60],
                        "sii_return": repr(fault),
                    }
                )
                session.write(summary_vals)
                new_cr.commit()
                new_cr.close()
                raise

    def _get_pos_order_number(self, pos_order):
        return pos_order.l10n_es_unique_id

    def _get_sorted_pos_orders(self):
        return self.order_ids.filtered(
            lambda order: order.state in ("paid", "done")
            and order.is_l10n_es_simplified_invoice
        ).sorted(key=lambda order: order.l10n_es_unique_id)

    def _get_sii_summary_dict(self):
        self.ensure_one()
        move = self.move_id
        pos_orders_sorted = self._get_sorted_pos_orders()
        first_order = pos_orders_sorted[:1]
        last_order = pos_orders_sorted[-1]
        number_ini = self._get_pos_order_number(first_order)[0:60]
        number_fin = self._get_pos_order_number(last_order)[0:60]
        ejercicio = fields.Date.from_string(move.date).year
        periodo = "%02d" % fields.Date.from_string(move.date).month
        company = self.company_id
        key = "01"
        pos_orders_amount_total = round(
            sum(pos_orders_sorted.mapped("amount_total")), 2
        )
        tipo_factura = "F4"
        session_date = move._change_date_format(move.date)
        if pos_orders_amount_total < 0:
            raise UserError(
                _("Negative session %s cannot be sent to SII") % (self.name)
            )
        taxes_dict, not_in_amount_total = self._get_sii_summary_taxes_from_move(
            pos_orders=pos_orders_sorted
        )
        importe_total = pos_orders_amount_total
        orders = {
            "IDFactura": {
                "IDEmisorFactura": {"NIF": company.vat[2:]},
                "NumSerieFacturaEmisor": number_ini,
                "FechaExpedicionFacturaEmisor": session_date,
                "NumSerieFacturaEmisorResumenFin": number_fin,
            },
            "PeriodoLiquidacion": {"Ejercicio": ejercicio, "Periodo": periodo},
            "FacturaExpedida": {
                "TipoFactura": tipo_factura,
                "ClaveRegimenEspecialOTrascendencia": key,
                "DescripcionOperacion": self.sii_description,
                "TipoDesglose": taxes_dict,
                "ImporteTotal": importe_total,
            },
        }
        if move.sii_macrodata:
            orders["FacturaExpedida"].update(Macrodato="S")
        return orders

    def _get_sii_summary_taxes_from_move(self, pos_orders=False):
        self.ensure_one()
        result = self.move_id.with_context(
            from_pos=True, pos_orders=pos_orders
        )._get_sii_out_taxes()
        return result

    def send_one_session(self):
        self.sudo()._process_send_summary_to_sii()

    def send_one_session_modification(self):
        self.sudo()._process_send_summary_to_sii(modification=True)

    def _validate_session(self):
        self.ensure_one()
        res = super(PosSession, self)._validate_session()
        company = self.company_id
        if (
            self.move_id
            and self.sii_state == "not_sent"
            and self.sii_enabled
            and company.sii_method == "auto"
            and company.use_connector
        ):
            self.send_sii()
        return res
