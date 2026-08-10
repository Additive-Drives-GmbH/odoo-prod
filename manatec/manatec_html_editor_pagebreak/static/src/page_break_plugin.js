import { Plugin } from "@html_editor/plugin";
import { closestBlock } from "@html_editor/utils/blocks";
import { closestElement, firstLeaf } from "@html_editor/utils/dom_traversal";
import { isEmptyBlock, isListItemElement, paragraphRelatedElementsSelector } from "@html_editor/utils/dom_info";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";
import { fillEmpty } from "@html_editor/utils/dom";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";

export class PageBreakPlugin extends Plugin {
    static id = "pageBreak";
    static dependencies = ["selection", "history", "split", "delete", "lineBreak", "baseContainer", "sanitize"];

    resources = {
        user_commands: [
            {
                id: "insertPageBreak",
                title: _t("Page Break"),
                description: _t("Insert a page break"),
                icon: "fa-scissors",
                run: this.insertPageBreak.bind(this),
                isAvailable: isHtmlContentSupported,
            },
        ],
        powerbox_items: withSequence(50, {
            categoryId: "structure",
            commandId: "insertPageBreak",
            keywords: [_t("page"), _t("break")],
        }),
        shorthands: [
            {
                pattern: /^\/pagebreak$/,
                commandId: "insertPageBreak",
            }
        ],
        content_not_editable_providers: (rootEl) => [...rootEl.querySelectorAll(".o_page_break")],
        contenteditable_to_remove_selector: ".o_page_break[contenteditable]",
    };

    insertPageBreak() {
        const selection = this.dependencies.selection.getSelectionData().deepEditableSelection;
        const block = closestBlock(selection.startContainer);
        const element =
            closestElement(selection.startContainer, paragraphRelatedElementsSelector) ||
            (block && !isListItemElement(block) ? block : null);

        if (element && element !== this.editable) {
            const pageBreak = this.document.createElement("div");
            pageBreak.className = "o_page_break";
            pageBreak.setAttribute("contenteditable", "false");
            pageBreak.textContent = _t("Page Break");

            const firstLeafNode = firstLeaf(block);
            if (
                isEmptyBlock(element) ||
                (selection.anchorNode === firstLeafNode && selection.anchorOffset === 0)
            ) {
                element.before(pageBreak);
            } else {
                element.after(pageBreak);
                const baseContainer = this.dependencies.baseContainer.createBaseContainer();
                fillEmpty(baseContainer);
                pageBreak.after(baseContainer);
                this.dependencies.selection.setCursorStart(baseContainer);
            }
        }
        this.dependencies.history.addStep();
    }
}

MAIN_PLUGINS.push(PageBreakPlugin);
