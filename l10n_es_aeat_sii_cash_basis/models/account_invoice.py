# -*- coding: utf-8 -*-
# Copyright 2018 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
import json
try:
    from odoo.addons.queue_job.job import job
except ImportError:
    logging.getLogger(__name__).debug('Can not `import queue_job`.')
    import functools

    def empty_decorator_factory(*argv, **kwargs):
        return functools.partial
    job = empty_decorator_factory


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    sii_cash_basis_sent = fields.Boolean(
        string='SII cash basis payment sent',
        copy=False,
        readonly=True,
    )
    sii_cash_basis_csv = fields.Char(
        string='SII cash basis payment CSV',
        copy=False,
        readonly=True,
    )
    sii_cash_basis_return = fields.Text(
        string='SII cash basis payment return',
        copy=False,
        readonly=True,
    )
    sii_cash_basis_send_failed = fields.Boolean(
        'SII cash basis send failed')
    sii_cash_basis_send_error = fields.Text(
        string='SII cash basis payment send error',
    )
    send_simultation_cash_basis_text = fields.Text('Simulación envío CC')
    send_simultation_invoice_text = fields.Text('Simulación envío Factura')

    def _register_hook(self):
        """Extend the WDSL and port name mapping for the new cases."""
        self.SII_WDSL_MAPPING.update({
            'out_invoice_payment': 'l10n_es_aeat_sii.wsdl_pr',
            'out_refund_payment': 'l10n_es_aeat_sii.wsdl_pr',
            'in_invoice_payment': 'l10n_es_aeat_sii.wsdl_ps',
            'in_refund_payment': 'l10n_es_aeat_sii.wsdl_ps',
        })
        self.SII_PORT_NAME_MAPPING.update({
            'out_invoice_payment': 'SuministroCobrosEmitidas',
            'out_refund_payment': 'SuministroCobrosEmitidas',
            'in_invoice_payment': 'SuministroPagosRecibidas',
            'in_refund_payment': 'SuministroPagosRecibidas',
        })
        return super(AccountInvoice, self)._register_hook()

    def _get_sii_payment_dict(self):
        """Prepare dictionary values for sending to SII."""
        self.ensure_one()
        # The actual payment date is tricky to be determined. Detected cases:
        #
        # * An account.payment record exists - Take the payment date.
        # * There's no payment record, but the other reconciled move is not
        #   linked to an invoice, so we assume this move has been created for
        #   for the payment and has the correct date.
        # * Any other case, default to reconcile creation date (=~now)
        invoice_payments = []
        lines = self.payment_move_line_ids
        payment_lines = lines.filtered(lambda x: x.invoice_id != self)
        invoice_date = self._change_date_format(self.date_invoice)
        for payment_line in payment_lines:
            sii_payment_mode = payment_line.payment_mode_id.sii_payment_mode_id
            if payment_line.payment_id:
                dt = payment_line.payment_id.payment_date
                sii_payment_mode = (
                    payment_line.payment_id.payment_method_id.sii_payment_mode_id
                )
            elif not payment_line.invoice_id:
                dt = payment_line.date
            else:
                dt = payment_line.create_date
            fecha = self._change_date_format(dt)
            if not sii_payment_mode:
                raise UserError(
                    _('No payment mode declared in the journal items to reconcile')
                )
            amount = payment_line.debit if self.type in (
                'out_refund', 'in_invoice') else payment_line.credit
            payment_details = {
                'Fecha': fecha,
                'Importe': amount,
                'Medio': sii_payment_mode.code,
            }
            invoice_payments.append(payment_details)
        if self.type in ['out_invoice', 'out_refund']:
            payment = {
                "IDFactura": {
                    "IDEmisorFactura": {
                        "NIF": self.company_id.vat[2:]
                    },
                    "NumSerieFacturaEmisor": self.number[0:60],
                    "FechaExpedicionFacturaEmisor": invoice_date,
                },
                "Cobros": {
                    "Cobro": invoice_payments,
                },
            }
        else:
            payment = {
                "IDFactura": {
                    "IDEmisorFactura": {
                        "NombreRazon": self.partner_id.name[0:120],
                    },
                    "NumSerieFacturaEmisor": (self.reference or '')[0:60],
                    "FechaExpedicionFacturaEmisor": invoice_date,
                },
                "Pagos": {
                    "Pago": invoice_payments,
                },
            }
            payment['IDFactura']['IDEmisorFactura'].update(
                self._get_sii_identifier()
            )
        return payment

    @job(default_channel='root.invoice_validate_sii')
    def send_cash_basis_payment(self):
        self.ensure_one()
        if self.sii_state == 'not_sent' or self.sii_registration_key.code != '07':
            raise UserError(
                _('La factura debe estar enviada al sii y tener clave 7.'))

        serv = self._connect_sii(self.type + '_payment')
        header = self._get_sii_header(False)
        inv_vals = {
            'sii_cash_basis_sent': False,
            'sii_cash_basis_send_error': False,
            'sii_cash_basis_send_failed': False,
        }
        if self.state == 'paid':
            inv_dict = self._get_sii_payment_dict()
        try:
            if self.type in ['out_invoice', 'out_refund']:
                res = serv.SuministroLRCobrosEmitidas(header, inv_dict)
            else:
                res = serv.SuministroLRPagosRecibidas(header, inv_dict)
            inv_vals['sii_cash_basis_return'] = res
            if res['EstadoEnvio'] in ['Correcto', 'AceptadoConErrores']:
                inv_vals.update({
                    'sii_cash_basis_sent': True,
                    'sii_cash_basis_csv': res['CSV'],
                })
            res_line = res['RespuestaLinea'][0]
            if res_line['CodigoErrorRegistro']:
                inv_vals['sii_cash_basis_send_error'] = u"{} | {}".format(
                    str(res_line['CodigoErrorRegistro']),
                    str(res_line['DescripcionErrorRegistro'])[:60],
                )
            self.write(inv_vals)
        except Exception as fault:
            new_cr = Registry(self.env.cr.dbname).cursor()
            env = api.Environment(new_cr, self.env.uid, self.env.context)
            invoice = env['account.invoice'].browse(self.id)
            inv_vals.update({
                'sii_cash_basis_send_failed': True,
                'sii_cash_basis_send_error': fault[:60],
                'sii_cash_basis_return': fault,
            })
            invoice.write(inv_vals)
            new_cr.commit()
            new_cr.close()
            raise

    @api.multi
    def send_simulation_cash_basis(self):
        # esto es para que podamos hacer pruebas de envío en test
        # y poder saber lo que se va a enviar
        # sin tener el certificado
        self.ensure_one()
        header = self._get_sii_header(False)
        inv_vals = {
            'sii_header_sent': json.dumps(header, indent=4),
            'sii_cash_basis_sent': False,
            'sii_cash_basis_send_error': False,
        }
        if self.state == 'paid':
            inv_dict = self._get_sii_payment_dict()
            inv_vals['sii_content_sent'] = json.dumps(inv_dict, indent=4)
            self.send_simultation_cash_basis_text = inv_vals['sii_content_sent']

    @api.multi
    def send_simulation_invoice(self):
        # esto es para que podamos hacer pruebas de envío en test
        # y poder saber lo que se va a enviar
        # sin tener el certificado
        self.ensure_one()
        if self.sii_state == 'not_sent':
            tipo_comunicacion = 'A0'
        else:
            tipo_comunicacion = 'A1'
        header = self._get_sii_header(tipo_comunicacion)
        inv_vals = {
            'sii_header_sent': json.dumps(header, indent=4),
        }
        inv_dict = self._get_sii_invoice_dict()
        inv_vals['sii_content_sent'] = json.dumps(inv_dict, indent=4)
        self.send_simultation_invoice_text = inv_vals['sii_content_sent']
        return True
