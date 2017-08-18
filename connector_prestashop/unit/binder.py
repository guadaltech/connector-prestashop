# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.connector.connector import Binder
from ..backend import prestashop
from odoo import models


@prestashop
class PrestashopBinder(Binder):
    """ Generic Binder for Prestashop """

    _external_field = 'prestashop_id'
    _openerp_field = 'odoo_id'

    _model_name = [
        'prestashop.shop.group',
        'prestashop.shop',
        'prestashop.res.partner',
        'prestashop.address',
        'prestashop.res.partner.category',
        'prestashop.res.lang',
        'prestashop.res.country',
        'prestashop.res.currency',
        'prestashop.account.tax',
        'prestashop.account.tax.group',
        'prestashop.product.category',
        'prestashop.product.image',
        'prestashop.product.template',
        'prestashop.product.combination',
        'prestashop.product.combination.option',
        'prestashop.product.combination.option.value',
        'prestashop.sale.order',
        'prestashop.sale.order.state',
        'prestashop.delivery.carrier',
        'prestashop.refund',
        'prestashop.supplier',
        'prestashop.product.supplierinfo',
        'prestashop.mail.message',
        'prestashop.groups.pricelist',
    ]

    def to_odoo(self, external_id, unwrap=False):
        # Make alias to to_openerp, remove in v10
        return self.to_openerp(external_id, unwrap)

    def to_backend(self, binding_id, wrap=False):
        """ Give the external ID for an OpenERP binding ID
        :param binding_id: OpenERP binding ID for which we want the backend id
        :param wrap: if False, binding_id is the ID of the binding,
                     if True, binding_id is the ID of the normal record, the
                     method will search the corresponding binding and returns
                     the backend id of the binding
        :return: external ID of the record
        """
        record = self.model.browse()
        if isinstance(binding_id, models.BaseModel):
            binding_id.ensure_one()
            record = binding_id
            binding_id = binding_id.id
        if wrap:
            binding = self.model.with_context(active_test=False).search(
                [(self._openerp_field, '=', binding_id),
                 (self._backend_field, '=', self.backend_record.id),
                 ]
            )
            if not binding:
                return None
            binding.ensure_one()
            return getattr(binding, self._external_field)
        if not record:
            record = self.model.browse(binding_id)
        assert record
        return getattr(record, self._external_field)
