/*global $*/

$(function () {
    var deleteSelectedTemplate = document.getElementById('delete-selected-with-vouchers-template');
    var coreDeleteBtn = $('.batch-select-actions button[name="action"][value="delete"]');
    if (deleteSelectedTemplate && coreDeleteBtn.length) {
        var deleteSelectedBtn = $(deleteSelectedTemplate.content.firstElementChild.cloneNode(true));
        var deleteSelectedCount = $('<span></span>').appendTo(deleteSelectedBtn);
        coreDeleteBtn.after(' ', deleteSelectedBtn);

        // Core's selection script only manages the buttons that existed when it ran, so mirror its state.
        var syncWithCoreDelete = function () {
            deleteSelectedBtn.prop('disabled', coreDeleteBtn.prop('disabled'));
            deleteSelectedCount.text(coreDeleteBtn.children('span').last().text());
        };
        new MutationObserver(syncWithCoreDelete).observe(coreDeleteBtn[0], {
            attributes: true, childList: true, subtree: true, characterData: true
        });
        syncWithCoreDelete();
    }
});
