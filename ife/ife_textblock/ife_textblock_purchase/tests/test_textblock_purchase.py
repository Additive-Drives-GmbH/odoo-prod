from odoo.tests.common import TransactionCase


class TestTextBlockPurchase(TransactionCase):
    def setUp(self):
        super().setUp()
        purchase_model = self.env["ir.model"]._get("purchase.order")
        self.pre_line_textblock = self.env["text.block"].create(
            {
                "textblock": "Pre Line TextBlock",
                "is_template": True,
                "res_model": "purchase.order",
                "text": "Pre Line TextBlock",
                "sequence": 1,
                "res_model_id": purchase_model.id,
            }
        )
        self.postline_textblock = self.env["text.block"].create(
            {
                "textblock": "Post Line Tetxblock",
                "is_template": True,
                "res_model": "purchase.order",
                "text": "Post Line Textblock",
                "sequence": 3,
                "res_model_id": purchase_model.id,
            }
        )

    def test_purchase_textblock_creation(self):
        # preline textblock
        self.assertEqual(self.pre_line_textblock.textblock, "Pre Line TextBlock")
        self.assertEqual(self.pre_line_textblock.is_template, True)
        # postline textblock
        self.assertEqual(self.postline_textblock.textblock, "Post Line Tetxblock")
        self.assertEqual(self.postline_textblock.is_template, True)

    def test_purchase_textblock_update(self):
        # preline textblock
        self.pre_line_textblock.write({"textblock": "Updated Preline TextBlock"})
        self.assertEqual(self.pre_line_textblock.textblock, "Updated Preline TextBlock")
        # postline textblock
        self.postline_textblock.write({"textblock": "Updated Postline TextBlock"})
        self.assertEqual(
            self.postline_textblock.textblock, "Updated Postline TextBlock"
        )

    def test_purchase_textblock_deletion(self):
        # preline textblock
        self.pre_line_textblock.unlink()
        textblock = self.env["text.block"].search(
            [("id", "=", self.pre_line_textblock.id)]
        )
        self.assertFalse(textblock)
        # postline textblock
        self.postline_textblock.unlink()
        textblock = self.env["text.block"].search(
            [("id", "=", self.postline_textblock.id)]
        )
        self.assertFalse(textblock)
