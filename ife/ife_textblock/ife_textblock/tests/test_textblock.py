from odoo.tests.common import TransactionCase


class TestTextBlock(TransactionCase):
    def setUp(self):
        super().setUp()
        product_template_model = self.env["ir.model"]._get("product.template")
        self.inline_textblock = self.env["text.block"].create(
            {
                "textblock": "TextBlock 1",
                "inline_check": True,
                "is_template": True,
                "res_model": "product.template",
                "text": "In Line Textblock",
                "sequence": 1,
                "res_model_id": product_template_model.id,
            }
        )
        self.preline_textblock = self.env["text.block"].create(
            {
                "textblock": "TextBlock 2",
                "preline_check": True,
                "is_template": True,
                "res_model": "product.template",
                "text": "Pre Line Textblock",
                "sequence": 2,
                "res_model_id": product_template_model.id,
            }
        )
        self.postline_textblock = self.env["text.block"].create(
            {
                "textblock": "TextBlock 3",
                "postline_check": True,
                "is_template": True,
                "res_model": "product.template",
                "text": "Post Line Textblock",
                "sequence": 3,
                "res_model_id": product_template_model.id,
            }
        )

    def test_textblock_creation(self):
        # inline textblock
        self.assertEqual(self.inline_textblock.textblock, "TextBlock 1")
        self.assertEqual(self.inline_textblock.is_template, True)
        # preline textblock
        self.assertEqual(self.preline_textblock.textblock, "TextBlock 2")
        self.assertEqual(self.preline_textblock.is_template, True)
        # postline textblock
        self.assertEqual(self.postline_textblock.textblock, "TextBlock 3")
        self.assertEqual(self.postline_textblock.is_template, True)

    def test_textblock_update(self):
        # inline textblock
        self.inline_textblock.write({"textblock": "Updated Inline TextBlock"})
        self.assertEqual(self.inline_textblock.textblock, "Updated Inline TextBlock")
        # preline textblock
        self.preline_textblock.write({"textblock": "Updated Preline TextBlock"})
        self.assertEqual(self.preline_textblock.textblock, "Updated Preline TextBlock")
        # postline textblock
        self.postline_textblock.write({"textblock": "Updated Postline TextBlock"})
        self.assertEqual(
            self.postline_textblock.textblock, "Updated Postline TextBlock"
        )

    def test_textblock_deletion(self):
        # inline textblock
        self.inline_textblock.unlink()
        textblock = self.env["text.block"].search(
            [("id", "=", self.inline_textblock.id)]
        )
        self.assertFalse(textblock)
        # preline textblock
        self.preline_textblock.unlink()
        textblock = self.env["text.block"].search(
            [("id", "=", self.preline_textblock.id)]
        )
        self.assertFalse(textblock)
        # postline textblock
        self.postline_textblock.unlink()
        textblock = self.env["text.block"].search(
            [("id", "=", self.postline_textblock.id)]
        )
        self.assertFalse(textblock)
