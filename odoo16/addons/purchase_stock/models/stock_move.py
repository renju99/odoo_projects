# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round, float_is_zero, float_compare
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    purchase_line_id = fields.Many2one(
        'purchase.order.line', 'Purchase Order Line',
        ondelete='set null', index='btree_not_null', readonly=True)
    created_purchase_line_id = fields.Many2one(
        'purchase.order.line', 'Created Purchase Order Line',
        ondelete='set null', index='btree_not_null', readonly=True, copy=False)

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        distinct_fields = super(StockMove, self)._prepare_merge_moves_distinct_fields()
        distinct_fields += ['purchase_line_id', 'created_purchase_line_id']
        return distinct_fields

    @api.model
    def _prepare_merge_negative_moves_excluded_distinct_fields(self):
        excluded_fields = super()._prepare_merge_negative_moves_excluded_distinct_fields() + ['created_purchase_line_id']
        if self.env['ir.config_parameter'].sudo().get_param('purchase_stock.merge_different_procurement'):
            excluded_fields += ['procure_method']
        return excluded_fields

    def _should_ignore_pol_price(self):
        self.ensure_one()
        return self.origin_returned_move_id or not self.purchase_line_id or not self.product_id.id

    def _get_price_unit(self):
        """ Returns the unit price for the move"""
        self.ensure_one()
        if self._should_ignore_pol_price():
            return super(StockMove, self)._get_price_unit()
        price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')
        line = self.purchase_line_id
        order = line.order_id
        received_qty = self._get_qty_received_without_self()
        if line.product_id.purchase_method == 'purchase' and float_compare(line.qty_invoiced, received_qty, precision_rounding=line.product_uom.rounding) > 0:
            move_layer = line.move_ids.sudo().stock_valuation_layer_ids
            invoiced_layer = line.sudo().invoice_lines.stock_valuation_layer_ids
            # value on valuation layer is in company's currency, while value on invoice line is in order's currency
            receipt_value = 0
            for layer in move_layer:
                if not layer._should_impact_price_unit_receipt_value():
                    continue
                receipt_value += layer.currency_id._convert(
                    layer.value, order.currency_id, order.company_id, layer.create_date, round=False)
            if invoiced_layer:
                receipt_value += sum(invoiced_layer.mapped(lambda l: l.currency_id._convert(
                    l.value, order.currency_id, order.company_id, l.create_date, round=False)))
            total_invoiced_value = 0
            invoiced_qty = 0
            for invoice_line in line.sudo().invoice_lines:
                if invoice_line.move_id.state != 'posted':
                    continue
                # Discount applied on bill prior to reception
                if invoice_line.discount:
                    price_unit = invoice_line.price_subtotal / invoice_line.quantity
                else:
                    price_unit = invoice_line.price_unit
                if invoice_line.tax_ids:
                    invoice_line_value = invoice_line.tax_ids.with_context(round=False).compute_all(
                        price_unit, currency=invoice_line.currency_id, quantity=invoice_line.quantity)['total_void']
                else:
                    invoice_line_value = price_unit * invoice_line.quantity
                total_invoiced_value += invoice_line.currency_id._convert(
                        invoice_line_value, order.currency_id, order.company_id, invoice_line.move_id.invoice_date, round=False)
                invoiced_qty += invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_id.uom_id, rounding_method="HALF-UP")
            # TODO currency check
            remaining_value = total_invoiced_value - receipt_value
            # TODO qty_received in product uom
            remaining_qty = invoiced_qty - line.product_uom._compute_quantity(received_qty, line.product_id.uom_id, rounding_method="HALF-UP")
            has_remaining = (
                not order.currency_id.is_zero(remaining_value)
                and not float_is_zero(remaining_qty, precision_rounding=line.product_id.uom_id.rounding)
            )
            if order.currency_id != order.company_id.currency_id and has_remaining:
                # will be rounded during currency conversion
                price_unit = remaining_value / remaining_qty
            elif has_remaining:
                price_unit = float_round(remaining_value / remaining_qty, precision_digits=price_unit_prec)
            else:
                price_unit = line._get_gross_price_unit()
        else:
            price_unit = line._get_gross_price_unit()
        if order.currency_id != order.company_id.currency_id:
            convert_date = self._get_currency_convert_date()
            price_unit = order.currency_id._convert(
                price_unit, order.company_id.currency_id, order.company_id, convert_date, round=False)
        return price_unit

    def _get_qty_received_without_self(self):
        qty_received = self.purchase_line_id.qty_received
        if self.state == 'done':
            qty_received -= self.product_uom._compute_quantity(
                self.quantity_done, self.purchase_line_id.product_uom, rounding_method='HALF-UP'
            )
        return qty_received

    def _get_currency_convert_date(self):
        self.ensure_one()
        # The date must be today, and not the date of the move since the move move is still
        # in assigned state. However, the move date is the scheduled date until move is
        # done, then date of actual move processing. See:
        # https://github.com/odoo/odoo/blob/2f789b6863407e63f90b3a2d4cc3be09815f7002/addons/stock/models/stock_move.py#L36
        convert_date = fields.Date.context_today(self) if self.state != 'done' else self.date
        line = self.purchase_line_id
        if not line:
            return convert_date

        # Use currency rate at bill date when invoice before receipt
        qty_received = self._get_qty_received_without_self()
        if float_compare(line.qty_invoiced, qty_received, precision_rounding=line.product_uom.rounding) > 0:
            posted_bills = line.sudo().invoice_lines.move_id.filtered(lambda m: m.state == 'posted')
            convert_date = max(posted_bills.mapped('invoice_date'), default=convert_date)
        return convert_date

    def _generate_valuation_lines_data(self, partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description):
        """ Overridden from stock_account to support amount_currency on valuation lines generated from po
        """
        self.ensure_one()

        rslt = super(StockMove, self)._generate_valuation_lines_data(partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description)
        purchase_currency = self.purchase_line_id.currency_id
        company_currency = self.company_id.currency_id
        if not self.purchase_line_id or purchase_currency == company_currency:
            return rslt
        svl = self.env['stock.valuation.layer'].browse(svl_id)
        if not svl.account_move_line_id:
            convert_date = self._get_currency_convert_date()
            rslt['credit_line_vals']['amount_currency'] = company_currency._convert(
                rslt['credit_line_vals']['balance'],
                purchase_currency,
                self.company_id,
                convert_date
            )
            rslt['debit_line_vals']['amount_currency'] = company_currency._convert(
                rslt['debit_line_vals']['balance'],
                purchase_currency,
                self.company_id,
                convert_date
            )
            rslt['debit_line_vals']['currency_id'] = purchase_currency.id
            rslt['credit_line_vals']['currency_id'] = purchase_currency.id
        else:
            rslt['credit_line_vals']['amount_currency'] = 0
            rslt['debit_line_vals']['amount_currency'] = 0
            rslt['debit_line_vals']['currency_id'] = purchase_currency.id
            rslt['credit_line_vals']['currency_id'] = purchase_currency.id
            if not svl.price_diff_value:
                return rslt
            # The idea is to force using the company currency during the reconciliation process
            rslt['debit_line_vals_curr'] = {
                'name': _("Currency exchange rate difference"),
                'product_id': self.product_id.id,
                'quantity': 0,
                'product_uom_id': self.product_id.uom_id.id,
                'partner_id': partner_id,
                'balance': 0,
                'account_id': debit_account_id,
                'currency_id': purchase_currency.id,
                'amount_currency': -svl.price_diff_value,
            }
            rslt['credit_line_vals_curr'] = {
                'name': _("Currency exchange rate difference"),
                'product_id': self.product_id.id,
                'quantity': 0,
                'product_uom_id': self.product_id.uom_id.id,
                'partner_id': partner_id,
                'balance': 0,
                'account_id': credit_account_id,
                'currency_id': purchase_currency.id,
                'amount_currency': svl.price_diff_value,
            }
        return rslt

    def _account_entry_move(self, qty, description, svl_id, cost):
        """
        In case of a PO return, if the value of the returned product is
        different from the purchased one, we need to empty the stock_in account
        with the difference
        """
        am_vals_list = super()._account_entry_move(qty, description, svl_id, cost)
        returned_move = self.origin_returned_move_id
        move = (self | returned_move).with_prefetch(self._prefetch_ids)
        pdiff_exists = bool(move.stock_valuation_layer_ids.stock_valuation_layer_ids.account_move_line_id)

        if not am_vals_list or not self.purchase_line_id or pdiff_exists or float_is_zero(qty, precision_rounding=self.product_id.uom_id.rounding):
            return am_vals_list

        layer = self.env['stock.valuation.layer'].browse(svl_id)

        if returned_move and self._is_out() and self._is_returned(valued_type='out'):
            returned_layer = returned_move.stock_valuation_layer_ids.filtered(lambda svl: not svl.stock_valuation_layer_id)[:1]
            returned_unit_cost = returned_layer.value / returned_layer.quantity
            layer_unit_cost = layer.value / layer.quantity
            unit_diff = layer_unit_cost - returned_unit_cost
        elif returned_move and returned_move._is_out() and returned_move._is_returned(valued_type='out'):
            returned_layer = returned_move.stock_valuation_layer_ids.filtered(lambda svl: not svl.stock_valuation_layer_id)[:1]
            unit_diff = returned_layer.unit_cost - self.purchase_line_id._get_gross_price_unit()
        else:
            return am_vals_list

        diff = unit_diff * qty
        company = self.purchase_line_id.company_id
        if company.currency_id.is_zero(diff):
            return am_vals_list

        sm = self.with_company(company).with_context(is_returned=True)
        accounts = sm.product_id.product_tmpl_id.get_product_accounts()
        acc_exp_id = accounts['expense'].id
        acc_stock_in_id = accounts['stock_input'].id
        journal_id = accounts['stock_journal'].id
        vals = sm._prepare_account_move_vals(acc_exp_id, acc_stock_in_id, journal_id, qty, description, False, diff)
        am_vals_list.append(vals)

        return am_vals_list

    def _prepare_extra_move_vals(self, qty):
        vals = super(StockMove, self)._prepare_extra_move_vals(qty)
        vals['purchase_line_id'] = self.purchase_line_id.id
        return vals

    def _prepare_move_split_vals(self, uom_qty):
        vals = super(StockMove, self)._prepare_move_split_vals(uom_qty)
        vals['purchase_line_id'] = self.purchase_line_id.id
        return vals

    def _clean_merged(self):
        super(StockMove, self)._clean_merged()
        self.write({'created_purchase_line_id': False})

    def _get_upstream_documents_and_responsibles(self, visited):
        if self.created_purchase_line_id and self.created_purchase_line_id.state not in ('done', 'cancel') \
                and (self.created_purchase_line_id.state != 'draft' or self._context.get('include_draft_documents')):
            return [(self.created_purchase_line_id.order_id, self.created_purchase_line_id.order_id.user_id, visited)]
        elif self.purchase_line_id and self.purchase_line_id.state not in ('done', 'cancel'):
            return[(self.purchase_line_id.order_id, self.purchase_line_id.order_id.user_id, visited)]
        else:
            return super(StockMove, self)._get_upstream_documents_and_responsibles(visited)

    def _get_related_invoices(self):
        """ Overridden to return the vendor bills related to this stock move.
        """
        rslt = super(StockMove, self)._get_related_invoices()
        purchase_ids = self.env['purchase.order'].search([('picking_ids', 'in', self.picking_id.ids)])
        rslt += purchase_ids.invoice_ids.filtered(lambda x: x.state == 'posted')
        return rslt

    def _get_source_document(self):
        res = super()._get_source_document()
        return self.purchase_line_id.order_id or res

    def _get_valuation_price_and_qty(self, related_aml, to_curr):
        valuation_price_unit_total = 0
        valuation_total_qty = 0
        for val_stock_move in self:
            # In case val_stock_move is a return move, its valuation entries have been made with the
            # currency rate corresponding to the original stock move
            valuation_date = val_stock_move.origin_returned_move_id.date or val_stock_move.date
            svl = val_stock_move.with_context(active_test=False).mapped('stock_valuation_layer_ids').filtered(
                lambda l: l.quantity)
            layers_qty = sum(svl.mapped('quantity'))
            layers_values = sum(svl.mapped('value'))
            valuation_price_unit_total += related_aml.company_currency_id._convert(
                layers_values, to_curr, related_aml.company_id, valuation_date, round=False,
            )
            valuation_total_qty += layers_qty
        if float_is_zero(valuation_total_qty, precision_rounding=related_aml.product_uom_id.rounding or related_aml.product_id.uom_id.rounding):
            raise UserError(
                _('Odoo is not able to generate the anglo saxon entries. The total valuation of %s is zero.') % related_aml.product_id.display_name)
        return valuation_price_unit_total, valuation_total_qty

    def _is_purchase_return(self):
        self.ensure_one()
        return self.location_dest_id.usage == "supplier" or self.location_dest_id == self.env.ref('stock.stock_location_inter_wh', raise_if_not_found=False)

    def _get_all_related_aml(self):
        # The back and for between account_move and account_move_line is necessary to catch the
        # additional lines from a cogs correction
        return super()._get_all_related_aml() | self.purchase_line_id.invoice_lines.move_id.line_ids.filtered(
            lambda aml: aml.product_id == self.purchase_line_id.product_id)

    def _get_all_related_sm(self, product):
        return super()._get_all_related_sm(product) | self.filtered(lambda m: m.purchase_line_id.product_id == product)
