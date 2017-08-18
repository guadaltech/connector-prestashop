.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=========================
Odoo PrestaShop Connector
=========================

This module connects Odoo and PrestaShop.

PrestaShop (http://www.prestashop.com/) is a popular e-commerce platform
written in PHP/MySQL and published under the Open Software licence v3.0.

This module allows the synchronization of the following objects from PrestaShop
to Odoo:

* Websites
* Stores and languages
* Carriers
* Product categories
* Products
* Partner categories
* Customers

Once these objects are synchronised, it will allow the import of sales orders,
together with the related customers.

As an extra feature, you can also export the stock quantities back to
PrestaShop.

If you want to export from Odoo to PrestaShop changes made on the products,
product categories or product images, you need to install
*connector_prestashop_catalog_manager* module in this same repository.

This connector supports PrestaShop version up to 1.6.11. Maybe later versions
are also supported, but they haven't been tested. It uses the webservices of
PrestaShop.

Installation
============

It doesn't require any plug-in in PrestaShop, but requires an extra Python
library in Odoo server side, called prestapyt:

https://github.com/prestapyt/prestapyt/

You can use pip install system to install it

`sudo pip install prestapyt`

Configuration
=============

To configure this module, you need to set several things in both PrestaShop
and Odoo:

Steps in PrestaShop
-------------------

#. Go to the control panel (usually at <url>/adminps).
#. Login into the system.
#. Go to *Advanced Parameters > Web service*
#. Add a new entry.
#. Generate a new API key that will be needed later.
#. Grant all the needed access according your security policy.

Steps in Odoo
-------------

#. Go to *Connectors > PrestaShop > Backends*.
#. Create a new record for registering a PrestaShop backend. You will bind
   this backend to an specific company and warehouse.
#. Define the main URL of the PrestaShop web, and the webservice key you
   got in PrestaShop.
#. Define other parameters like the discount and shipping products, or if the
   taxes are included in the price.
#. Click on "Synchronize Metadata" button. This will bring the basic shop
   information that you can find on *Websites* and *Stores* menus.
#. Click on "Synchronize Base Data" button. This will import carriers,
   languages, tax groups and the rest of base data that are needed for the
   proper work.
#. Go to *Accounting > Configuration > Taxes > Tax Groups*, and include
   for each of the tax definition imported from PrestaShop, the corresponding
   taxes in Odoo.
#. Activate the job runner, checking the connector documentation for setting
   the server correctly for using it in
   http://odoo-connector.com/guides/jobrunner.html
#. Alternatively, if you are not able to activate it, you can enable the
   scheduled job called "Enqueue Jobs".
#. Activate the scheduled jobs for importing the records you want:

  * PrestaShop - Export Stock Quantities
  * PrestaShop - Import Carriers
  * PrestaShop - Import Customers and Groups
  * PrestaShop - Import Products and Categories
  * PrestaShop - Import Sales Orders
  * PrestaShop - Import suppliers

   :target: https://runbot.odoo-community.org/runbot/108/9.0

Test dependencies
=================

Extra libs are required to run the tests:
* ``vcrpy``
* ``freezegun``

Todo
=================

Product Images

