# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields

from ...unit.backend_adapter import GenericAdapter
from ...backend import prestashop

#Hilos
class SaleOrderThread(models.Model):
    _name = 'sale.order.thread'

    prestashop_bind_ids = fields.One2many(
        comodel_name='prestashop.sale.order.thread',
        inverse_name='odoo_id',
        string='PrestaShop Bindings',
    )

    order_id = fields.Many2one(
        comodel_name='sale.order',
        required=True,
        ondelete='cascade',
        string='Message'
    )

class PrestashopSaleOrderThread(models.Model):
    _name = "prestashop.sale.order.thread"
    _inherit = "prestashop.binding.odoo"
    _inherits = {'sale.order.thread': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='sale.order.thread',
        required=True,
        ondelete='cascade',
        string='Message'
    )

@prestashop
class SaleOrderThreadAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order.thread'
    _prestashop_model = 'customer_threads'

#Mensajes
class SaleOrderMessage(models.Model):
    _name = 'sale.order.message'

    prestashop_bind_ids = fields.One2many(
        comodel_name='prestashop.sale.order.message',
        inverse_name='odoo_id',
        string='PrestaShop Bindings',
    )

    thread_id = fields.Many2one(
        comodel_name='sale.order.thread',
        required=True,
        ondelete='cascade',
        string='Message'
    )

    message = fields.Text(
        string='Mensaje'
    )

class PrestashopSaleOrderMessage(models.Model):
    _name = "prestashop.sale.order.message"
    _inherit = "prestashop.binding.odoo"
    _inherits = {'sale.order.message': 'odoo_id'}

    odoo_id = fields.Many2one(
        comodel_name='sale.order.message',
        required=True,
        ondelete='cascade',
        string='Message'
    )


@prestashop
class SaleOrderMessageAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order.message'
    _prestashop_model = 'customer_messages'
