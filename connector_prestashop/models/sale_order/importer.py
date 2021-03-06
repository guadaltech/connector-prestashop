# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import _, fields, tools
from odoo.addons.queue_job.job import job
from odoo.addons.connector.connector import ConnectorUnit
from odoo.addons.queue_job.exception import FailedJobError, NothingToDoJob
from odoo.addons.connector.unit.mapper import ImportMapper, mapping
from odoo.addons.connector_ecommerce.unit.sale_order_onchange import (
    SaleOrderOnChange,
)
from ...unit.backend_adapter import GenericAdapter
from ...unit.importer import (
    PrestashopImporter,
    import_batch,
    DelayedBatchImporter,
)
from ...unit.exception import OrderImportRuleRetry
from ...backend import prestashop

from datetime import datetime, timedelta
from decimal import Decimal
import logging
_logger = logging.getLogger(__name__)

try:
    from prestapyt import PrestaShopWebServiceError
except:
    _logger.debug('Cannot import from `prestapyt`')


@prestashop
class PrestaShopSaleOrderOnChange(SaleOrderOnChange):
    _model_name = 'prestashop.sale.order'


@prestashop
class SaleImportRule(ConnectorUnit):
    _model_name = ['prestashop.sale.order']

    def _rule_always(self, record, mode):
        """ Always import the order """
        return True

    def _rule_never(self, record, mode):
        """ Never import the order """
        raise NothingToDoJob('Orders with payment modes %s '
                             'are never imported.' %
                             record['payment']['method'])

    def _rule_paid(self, record, mode):
        """ Import the order only if it has received a payment """
        if self._get_paid_amount(record) == 0.0:
            raise OrderImportRuleRetry('The order has not been paid.\n'
                                       'The import will be retried later.')

    def _get_paid_amount(self, record):
        payment_adapter = self.unit_for(
            GenericAdapter,
            '__not_exist_prestashop.payment'
        )
        payment_ids = payment_adapter.search({
            'filter[order_reference]': record['reference']
        })
        paid_amount = 0.0
        for payment_id in payment_ids:
            payment = payment_adapter.read(payment_id)
            paid_amount += float(payment['amount'])
        return paid_amount

    _rules = {
        'always': _rule_always,
        'paid': _rule_paid,
        'authorized': _rule_paid,
        'never': _rule_never,
    }

    def check(self, record):
        """ Check whether the current sale order should be imported
        or not. It will actually use the payment mode configuration
        and see if the chosen rule is fullfilled.

        :returns: True if the sale order should be imported
        :rtype: boolean
        """
        ps_payment_method = record['payment']
        mode_binder = self.binder_for('account.payment.mode')
        if type(ps_payment_method) == str:
            payment_mode = self.to_internal_account_payment_mode(ps_payment_method)
        else:
            payment_mode = mode_binder.to_internal(ps_payment_method)
        if not payment_mode:
            raise FailedJobError(_(
                "The configuration is missing for the Payment Mode '%s'.\n\n"
                "Resolution:\n"
                " - Use the automatic import in 'Connectors > PrestaShop "
                "Backends', button 'Import payment modes', or:\n"
                "\n"
                "- Go to 'Invoicing > Configuration > Management "
                "> Payment Modes'\n"
                "- Create a new Payment Mode with name '%s'\n"
                "-Eventually  link the Payment Method to an existing Workflow "
                "Process or create a new one.") % (ps_payment_method,
                                                   ps_payment_method))
        self._rule_global(record, payment_mode)
        self._rules[payment_mode.import_rule](self, record, payment_mode)

    def _rule_global(self, record, mode):
        """ Rule always executed, whichever is the selected rule """
        order_id = record['id']
        max_days = mode.days_before_cancel
        if not max_days:
            return
        if self._get_paid_amount(record) != 0.0:
            return
        fmt = '%Y-%m-%d %H:%M:%S'
        order_date = datetime.strptime(record['date_add'], fmt)
        if order_date + timedelta(days=max_days) < datetime.now():
            raise NothingToDoJob('Import of the order %s canceled '
                                 'because it has not been paid since %d '
                                 'days' % (order_id, max_days))

    def to_internal_account_payment_mode(self, external_id, unwrap=False):
        """ Give the Odoo recordset for an external ID

        :param external_id: external ID for which we want
                            the Odoo ID
        :param unwrap: if True, returns the normal record
                       else return the binding record
        :return: a recordset, depending on the value of unwrap,
                 or an empty recordset if the external_id is not mapped
        :rtype: recordset
        """
        bindings = self.env['account.payment.mode'].with_context(active_test=False).search(
            [('name', '=', tools.ustr(external_id))]
        )
        if not bindings:
            if unwrap:
                return self.model.browse()[self._odoo_field]
            return self.model.browse()
        bindings.ensure_one()
        if unwrap:
            bindings = bindings[self._odoo_field]
        return bindings


@prestashop
class SaleOrderMapper(ImportMapper):
    _model_name = 'prestashop.sale.order'

    direct = [
        ('date_add', 'date_order'),
        ('invoice_number', 'prestashop_invoice_number'),
        ('delivery_number', 'prestashop_delivery_number'),
        ('total_paid', 'total_amount'),
        ('total_shipping_tax_incl', 'total_shipping_tax_included'),
        ('total_shipping_tax_excl', 'total_shipping_tax_excluded')
    ]

    def _get_sale_order_lines(self, record):
        orders = record['associations'].get(
            'order_rows', {}).get(
            self.backend_record.get_version_ps_key('order_row'), [])
        if isinstance(orders, dict):
            return [orders]
        return orders

    def _get_discounts_lines(self, record):
        if record['total_discounts'] == '0.00':
            return []
        adapter = self.unit_for(
            GenericAdapter, 'prestashop.sale.order.line.discount')
        discount_ids = adapter.search({'filter[id_order]': record['id']})
        discount_mappers = []
        for discount_id in discount_ids:
            discount_mappers.append({'id': discount_id})
        return discount_mappers

    children = [
        (_get_sale_order_lines,
         'prestashop_order_line_ids', 'prestashop.sale.order.line'),
        (_get_discounts_lines,
         'prestashop_discount_line_ids', 'prestashop.sale.order.line.discount')
    ]

    def _map_child(self, map_record, from_attr, to_attr, model_name):
        source = map_record.source
        # TODO patch ImportMapper in connector to support callable
        if callable(from_attr):
            child_records = from_attr(self, source)
        else:
            child_records = source[from_attr]

        children = []
        for child_record in child_records:
            adapter = self.unit_for(GenericAdapter, model_name)
            detail_record = adapter.read(child_record['id'])

            mapper = self._get_map_child_unit(model_name)
            items = mapper.get_items(
                [detail_record], map_record, to_attr, options=self.options
            )
            children.extend(items)
        return children

    def _sale_order_exists(self, name):
        sale_order = self.env['sale.order'].search([
            ('name', '=', name),
            ('company_id', '=', self.backend_record.company_id.id),
        ], limit=1)
        return len(sale_order) == 1

    @mapping
    def name(self, record):
        basename = record['reference']
        if not self._sale_order_exists(basename):
            return {"name": basename}
        i = 1
        name = basename + '_%d' % (i)
        while self._sale_order_exists(name):
            i += 1
            name = basename + '_%d' % (i)
        return {"name": name}

    @mapping
    def partner_id(self, record):
        binder = self.binder_for('prestashop.res.partner')
        partner = binder.to_internal(record['id_customer'], unwrap=True)
        return {'partner_id': partner.id}

    @mapping
    def partner_invoice_id(self, record):
        binder = self.binder_for('prestashop.address')
        address = binder.to_internal(record['id_address_invoice'], unwrap=True)
        return {'partner_invoice_id': address.id}

    @mapping
    def partner_shipping_id(self, record):
        binder = self.binder_for('prestashop.address')
        shipping = binder.to_internal(record['id_address_delivery'], unwrap=True)
        return {'partner_shipping_id': shipping.id}

    @mapping
    def pricelist_id(self, record):
        return {'pricelist_id': self.backend_record.pricelist_id.id}

    @mapping
    def sale_team(self, record):
        if self.backend_record.sale_team_id:
            return {'team_id': self.backend_record.sale_team_id.id}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def payment(self, record):
        binder = self.binder_for('account.payment.mode')
        if type(record['payment']) != str:
            mode = binder.to_internal(record['payment'])
        else:
            mode = self.to_internal_account_payment_mode_res(record['payment'])
        assert mode, ("import of error fail in SaleImportRule.check "
                      "when the payment mode is missing")
        return {'payment_mode_id': mode.id}

    def to_internal_account_payment_mode_res(self, external_id, unwrap=False):
        """ Give the Odoo recordset for an external ID

        :param external_id: external ID for which we want
                            the Odoo ID
        :param unwrap: if True, returns the normal record
                       else return the binding record
        :return: a recordset, depending on the value of unwrap,
                 or an empty recordset if the external_id is not mapped
        :rtype: recordset
        """
        bindings = self.env['account.payment.mode'].with_context(active_test=False).search(
            [('name', '=', tools.ustr(external_id))]
        )
        if not bindings:
            if unwrap:
                return self.model.browse()[self._odoo_field]
            return self.model.browse()
        bindings.ensure_one()
        if unwrap:
            bindings = bindings[self._odoo_field]
        return bindings

    @mapping
    def carrier_id(self, record):
        if record['id_carrier'] == '0':
            return {}
        binder = self.binder_for('prestashop.delivery.carrier')
        carrier = binder.to_internal(record['id_carrier'], unwrap=True)
        return {'carrier_id': carrier.id}

    @mapping
    def total_tax_amount(self, record):
        tax = (float(record['total_paid_tax_incl']) -
               float(record['total_paid_tax_excl']))
        return {'total_amount_tax': tax}

    def finalize(self, map_record, values):
        onchange = self.unit_for(SaleOrderOnChange)
        return onchange.play(values, values['prestashop_order_line_ids'])


@prestashop
class SaleOrderImporter(PrestashopImporter):
    _model_name = ['prestashop.sale.order']

    def __init__(self, environment):
        """
        :param environment: current environment (backend, session, ...)
        :type environment: :py:class:`connector.connector.ConnectorEnvironment`
        """
        super(SaleOrderImporter, self).__init__(environment)
        self.line_template_errors = []

    def _import_dependencies(self):
        record = self.prestashop_record
        self._import_dependency(
            record['id_customer'], 'prestashop.res.partner'
        )
        self._import_dependency(
            record['id_address_invoice'], 'prestashop.address'
        )
        self._import_dependency(
            record['id_address_delivery'], 'prestashop.address'
        )

        if record['id_carrier'] != '0':
            self._import_dependency(record['id_carrier'],
                                    'prestashop.delivery.carrier')

        rows = record['associations'] \
            .get('order_rows', {}) \
            .get(self.backend_record.get_version_ps_key('order_row'), [])
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows:
            try:
                self._import_dependency(row['product_id'],
                                        'prestashop.product.template')
            except PrestaShopWebServiceError as err:
                # we ignore it, the order line will be imported without product
                _logger.error('PrestaShop product %s could not be imported, '
                              'error: %s', row['product_id'], err)
                self.line_template_errors.append(row)
                print self.line_template_errors

    def _add_shipping_line(self, binding):
        shipping_total = (binding.total_shipping_tax_included
                          if self.backend_record.taxes_included
                          else binding.total_shipping_tax_excluded)
        # when we have a carrier_id, even with a 0.0 price,
        # Odoo will adda a shipping line in the SO when the picking
        # is done, so we better add the line directly even when the
        # price is 0.0
        if binding.odoo_id.carrier_id:
            binding.odoo_id._create_delivery_line(
                binding.odoo_id.carrier_id,
                shipping_total
            )
        binding.odoo_id.recompute()

    def _after_import(self, binding):
        super(SaleOrderImporter, self)._after_import(binding)
        self._add_shipping_line(binding)
        self.checkpoint_line_without_template(binding)

    def checkpoint_line_without_template(self, binding):
        if not self.line_template_errors:
            return
        msg = _('Product(s) used in the sales order could not be imported.')
        self.backend_record.add_checkpoint(
            model='sale.order',
            record_id=binding.odoo_id.id,
            message=msg,
        )

    def _has_to_skip(self):
        """ Return True if the import can be skipped """
        if self._get_binding():
            return True
        rules = self.unit_for(SaleImportRule)
        try:
            return rules.check(self.prestashop_record)
        except NothingToDoJob as err:
            # we don't let the NothingToDoJob exception let go out, because if
            # we are in a cascaded import, it would stop the whole
            # synchronization and set the whole job to done
            return err.message


@prestashop
class SaleOrderBatchImporter(DelayedBatchImporter):
    _model_name = 'prestashop.sale.order'


@prestashop
class SaleOrderLineMapper(ImportMapper):
    _model_name = 'prestashop.sale.order.line'

    direct = [
        ('product_name', 'name'),
        ('id', 'sequence'),
        ('product_quantity', 'product_uom_qty'),
        ('reduction_percent', 'discount'),
    ]

    @mapping
    def prestashop_id(self, record):
        return {'prestashop_id': record['id']}

    @mapping
    def price_unit(self, record):
        if self.backend_record.taxes_included:
            key = 'unit_price_tax_incl'
        else:
            key = 'unit_price_tax_excl'
        if record['reduction_percent']:
            reduction = Decimal(record['reduction_percent'])
            price = Decimal(record[key])
            price_unit = price / ((100 - reduction) / 100)
        else:
            price_unit = record[key]
        return {'price_unit': price_unit}

    @mapping
    def product_id(self, record):
        if int(record.get('product_attribute_id', 0)):
            combination_binder = self.binder_for(
                'prestashop.product.combination'
            )
            product = combination_binder.to_internal(
                record['product_attribute_id'],
                unwrap=True,
            )
        else:
            binder = self.binder_for('prestashop.product.template')
            template = binder.to_internal(record['product_id'], unwrap=True)
            product = self.env['product.product'].search([
                ('product_tmpl_id', '=', template.id),
                ('company_id', '=', self.backend_record.company_id.id)],
                limit=1,
            )
        if not product:
            return {}
        return {
            'product_id': product.id,
            'product_uom': product and product.uom_id.id,
        }

    def _find_tax(self, ps_tax_id):
        binder = self.binder_for('prestashop.account.tax')
        return binder.to_internal(ps_tax_id, unwrap=True)

    @mapping
    def tax_id(self, record):
        taxes = record.get('associations', {}).get('taxes', {}).get(
            self.backend_record.get_version_ps_key('tax'), [])
        if not isinstance(taxes, list):
            taxes = [taxes]
        result = self.env['account.tax'].browse()
        for ps_tax in taxes:
            result |= self._find_tax(ps_tax['id'])
        if result:
            return {'tax_id': [(6, 0, result.ids)]}
        return {}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}


@prestashop
class SaleOrderLineDiscountMapper(ImportMapper):
    _model_name = 'prestashop.sale.order.line.discount'

    direct = []

    @mapping
    def discount(self, record):
        return {
            'name': record['name'],
            'product_uom_qty': 1,
        }

    @mapping
    def price_unit(self, record):
        if self.backend_record.taxes_included:
            price_unit = record['value']
        else:
            price_unit = record['value_tax_excl']
        if price_unit[0] != '-':
            price_unit = '-' + price_unit
        return {'price_unit': price_unit}

    @mapping
    def product_id(self, record):
        if self.backend_record.discount_product_id:
            return {'product_id': self.backend_record.discount_product_id.id}
        product_discount = self.session.env.ref(
            'connector_ecommerce.product_product_discount')
        return {'product_id': product_discount.id}

    @mapping
    def tax_id(self, record):
        return {'tax_id': [
            (6, 0, self.backend_record.discount_product_id.taxes_id.ids)
        ]}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def prestashop_id(self, record):
        return {'prestashop_id': record['id']}


@job(default_channel='root.prestashop')
def import_orders_since(session, backend_id, since_date=None, **kwargs):
    """ Prepare the import of orders modified on PrestaShop """
    backend_record = session.env['prestashop.backend'].browse(backend_id)
    filters = None
    if since_date:
        filters = {'date': '1', 'filter[date_upd]': '>[%s]' % (since_date)}
    result = import_batch(
        session,
        'prestashop.sale.order',
        backend_id,
        filters,
        priority=10,
        max_retries=0,
        **kwargs
    )
    if since_date:
        filters = {'date': '1', 'filter[date_add]': '>[%s]' % since_date}
    try:
        import_batch(session, 'prestashop.mail.message', backend_id, filters)
    except Exception as error:
        msg = _(
            'Mail messages import failed with filters `%s`. '
            'Error: `%s`'
        ) % (str(filters), str(error))
        backend_record.add_checkpoint(
            message=msg
        )

    now_fmt = fields.Datetime.now()
    backend_record.write({
        'import_orders_since': now_fmt
    })
    return result
