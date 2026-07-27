# -*- coding: utf-8 -*-
"""
    Author: Denis Orechov (denis.orechov@manatec.de)
    Copyright: 2026, manaTec GmbH
    Date created: 27.07.2026
"""

from odoo import fields, models
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "ADD_distribution_display_sale")
class TestAnalyticDistributionDisplay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.product = cls.env["product.product"].create({"name": "Test Product"})
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
        })
        cls.plan1 = cls.env["account.analytic.plan"].create({
            "name": "Plan 1",
            "sequence": 10,
        })
        cls.plan2 = cls.env["account.analytic.plan"].create({
            "name": "Plan 2",
            "sequence": 20,
        })
        cls.acc1 = cls.env["account.analytic.account"].create({
            "name": "Account A",
            "plan_id": cls.plan1.id,
        })
        cls.acc2 = cls.env["account.analytic.account"].create({
            "name": "Account B",
            "plan_id": cls.plan1.id,
        })
        cls.acc3 = cls.env["account.analytic.account"].create({
            "name": "Account C",
            "plan_id": cls.plan2.id,
        })
        cls.archived_acc = cls.env["account.analytic.account"].create({
            "name": "Archived Account",
            "plan_id": cls.plan1.id,
            "active": False,
        })

    def test_01_empty_distribution(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {}
        })
        self.assertEqual(line.analytic_account_display, "")

    def test_02_single_account(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {str(self.acc1.id): 100.0}
        })
        self.assertEqual(line.analytic_account_display, "Account A")

    def test_03_multiple_accounts_one_plan(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {
                str(self.acc1.id): 40.0,
                str(self.acc2.id): 60.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Account B (60%) | Account A (40%)")

    def test_04_multiple_plans(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {
                str(self.acc1.id): 100.0,
                str(self.acc3.id): 100.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Account A | Account C")

    def test_05_orphaned_account(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {
                "999999": 100.0,
                str(self.acc1.id): 100.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Account A")

    def test_06_archived_account(self):
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {
                str(self.archived_acc.id): 100.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Archived Account")

    def test_distribution_same_value(self):
        # Test case: {'123,234': 100.0}
        line = self.env["sale.order.line"].create({
            "order_id": self.order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "product_uom": self.product.uom_id.id,
            "price_unit": 10.0,
            "name": "Test Line",
            "analytic_distribution": {f"{self.acc1.id},{self.acc2.id}": 100.0}
        })

        # Expected behavior: both accounts are displayed with their percentage
        # The expected string depends on how analytic_distribution_display_mixin formats it.
        # Based on previous tests, it should include both accounts.
        display = line.analytic_account_display
        self.assertTrue(display)
        self.assertIn("Account A", display)
        self.assertIn("Account B", display)
