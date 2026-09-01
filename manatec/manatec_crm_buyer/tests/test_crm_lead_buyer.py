# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "ADD_crm_buyer")
class TestCrmLeadBuyer(TransactionCase):

    def test_01_set_buyer_with_email(self):
        partner = self.env["res.partner"].create({
            "name": "Buyer Contact",
            "email": "buyer@example.com",
        })
        lead = self.env["crm.lead"].create({
            "name": "Test Lead",
            "buyer_id": partner.id,
        })
        self.assertEqual(lead.buyer_id, partner)
        self.assertEqual(lead.buyer_email, partner.email)

    def test_02_remove_buyer_email(self):
        partner = self.env["res.partner"].create({
            "name": "Buyer Contact",
            "email": "buyer@example.com",
        })
        lead = self.env["crm.lead"].create({
            "name": "Test Lead",
            "buyer_id": partner.id,
        })
        self.assertEqual(lead.buyer_email, partner.email)

        partner.email = False
        self.assertFalse(lead.buyer_email)

    def test_03_remove_buyer(self):
        partner = self.env["res.partner"].create({
            "name": "Buyer Contact",
            "email": "buyer@example.com",
        })
        lead = self.env["crm.lead"].create({
            "name": "Test Lead",
            "buyer_id": partner.id,
        })
        self.assertEqual(lead.buyer_id, partner)
        self.assertEqual(lead.buyer_email, partner.email)

        lead.buyer_id = False
        self.assertFalse(lead.buyer_id)
        self.assertFalse(lead.buyer_email)
