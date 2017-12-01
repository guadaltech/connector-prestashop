# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.connector.unit.mapper import ImportMapper, mapping
from ...unit.importer import PrestashopImporter, DelayedBatchImporter
from ...backend import prestashop

#Hilos
@prestashop
class SaleOrderThreadMapper(ImportMapper):
    _model_name = 'prestashop.sale.order.thread'

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def object_ref(self, record):
        binder = self.binder_for('prestashop.sale.order')
        order = binder.to_internal(record['id_order'], unwrap=True)
        return {
            'order_id': order.id,
        }

    @mapping
    def author_id(self, record):
        if record['id_customer'] != '0':
            binder = self.binder_for('prestashop.res.partner')
            partner = binder.to_internal(record['id_customer'], unwrap=True)
            return {'author_id': partner.id}
        return {}


@prestashop
class SaleOrderThreadImporter(PrestashopImporter):
    """ Import one simple record """
    _model_name = 'prestashop.sale.order.thread'

    def _import_dependencies(self):
        record = self.prestashop_record
        self._import_dependency(record['id_order'], 'prestashop.sale.order')
        if record['id_customer'] != '0':
            self._import_dependency(
                record['id_customer'], 'prestashop.res.partner'
            )

    def _has_to_skip(self):
        record = self.prestashop_record
        if not record.get('id_order'):
            return 'no id_order'
        binder = self.binder_for('prestashop.sale.order')
        order_binding = binder.to_internal(record['id_order'])
        return record['id_order'] == '0' or not order_binding


@prestashop
class SaleOrderThreadBatchImporter(DelayedBatchImporter):
    _model_name = 'prestashop.sale.order.thread'


#Mensajes
@prestashop
class SaleOrderMessageMapper(ImportMapper):
    _model_name = 'prestashop.sale.order.message'

    direct = [
        ('message', 'message')
    ]

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def object_ref(self, record):
        binder = self.binder_for('prestashop.sale.order.thread')
        order = binder.to_internal(record['id_customer_thread'], unwrap=True)
        return {
            'thread_id': order.id,
        }


@prestashop
class SaleOrderMessageImporter(PrestashopImporter):
    """ Import one simple record """
    _model_name = 'prestashop.sale.order.message'

    def _import_dependencies(self):
        record = self.prestashop_record
        self._import_dependency(record['id_customer_thread'], 'prestashop.sale.order.thread')

    def _has_to_skip(self):
        record = self.prestashop_record
        if not record.get('id_customer_thread'):
            return 'no id_customer_thread'
        binder = self.binder_for('prestashop.sale.order.thread')
        order_binding = binder.to_internal(record['id_customer_thread'])
        return record['id_customer_thread'] == '0' or not order_binding


@prestashop
class SaleOrderMessageBatchImporter(DelayedBatchImporter):
    _model_name = 'prestashop.sale.order.message'


