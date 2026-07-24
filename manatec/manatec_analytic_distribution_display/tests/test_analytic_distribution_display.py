from odoo import fields, models
from odoo.tests.common import TransactionCase, tagged


class AnalyticDistributionTestLine(models.Model):
    _name = "analytic.distribution.test.line"
    _description = "Analytic Distribution Test Line"
    _inherit = ["analytic.distribution.display.mixin"]

    analytic_distribution = fields.Json(string="Analytic Distribution")


@tagged("post_install", "-at_install")
class TestAnalyticDistributionDisplay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        line = self.env["analytic.distribution.test.line"].create({
            "analytic_distribution": {}
        })
        self.assertEqual(line.analytic_account_display, "")

    def test_02_single_account(self):
        line = self.env["analytic.distribution.test.line"].create({
            "analytic_distribution": {str(self.acc1.id): 100.0}
        })
        self.assertEqual(line.analytic_account_display, "Account A")

    def test_03_multiple_accounts_one_plan(self):
        line = self.env["analytic.distribution.test.line"].create({
            "analytic_distribution": {
                str(self.acc1.id): 40.0,
                str(self.acc2.id): 60.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Account B (60%) | Account A (40%)")

    def test_04_multiple_plans(self):
        line = self.env["analytic.distribution.test.line"].create({
            "analytic_distribution": {
                str(self.acc1.id): 100.0,
                str(self.acc3.id): 100.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Account A | Account C")

    def test_05_orphaned_account(self):
        line = self.env["analytic.distribution.test.line"].create({
            "analytic_distribution": {
                "999999": 100.0,
                str(self.acc1.id): 100.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Account A")

    def test_06_archived_account(self):
        line = self.env["analytic.distribution.test.line"].create({
            "analytic_distribution": {
                str(self.archived_acc.id): 100.0,
            }
        })
        self.assertEqual(line.analytic_account_display, "Archived Account")
