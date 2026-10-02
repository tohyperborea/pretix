/*global $,gettext*/

$(function () {
    var runLotteryBtn = $('#run-lottery-btn');
    var revertListBtn = $('#revert-list-btn');
    var itemSelect = $('select[name="item"]');
    var confirmModal = $('#lottery-confirm-modal');
    var modalTitle = $('#lottery-modal-title');
    var modalDescription = $('#lottery-modal-description');
    var productContainer = $('#lottery-product-container');
    var productNameSpan = $('#lottery-product-name');
    var modalWarning = $('#lottery-modal-warning');
    var confirmBtn = $('#lottery-confirm-btn');
    var actionUrl = null;

    // Vouchers are sent by running the lottery, not by core's "Send as many vouchers as possible".
    $('form[action$="/waitinglist/auto_assign"] button[type="submit"]').prop('disabled', true);
    // Priorities come from the lottery; hide manual move to top / end so they can't be changed by accident.
    $('button[name="move_top"], button[name="move_end"], button.disabled:has(.fa-thumbs-up), button.disabled:has(.fa-thumbs-down)').remove();

    function buildFilterParams() {
        var urlParams = new URLSearchParams();
        var currentParams = new URLSearchParams(window.location.search);

        if (currentParams.has('status')) {
            urlParams.set('status', currentParams.get('status'));
        }
        if (currentParams.has('subevent')) {
            urlParams.set('subevent', currentParams.get('subevent'));
        }
        return urlParams;
    }

    function showConfirmationModal(config) {
        modalTitle.text(config.title);
        modalDescription.text(config.description);
        modalWarning.text(config.warning);
        confirmBtn.text(config.confirmButtonText);

        if (config.showProduct) {
            productContainer.show();
            productNameSpan.text(config.productName);
        } else {
            productContainer.hide();
        }

        confirmModal.modal('show');
    }

    if (runLotteryBtn.length && itemSelect.length) {
        runLotteryBtn.on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            var selectedItemId = itemSelect.val();
            var selectedItemText = itemSelect.find('option:selected').text();

            if (!selectedItemId || selectedItemId === '' || selectedItemId === null || selectedItemId === undefined) {
                alert(gettext('You must select a specific product to run the lottery. Please select a product from the dropdown and try again.'));
                return false;
            }

            var urlParams = buildFilterParams();
            urlParams.set('item', selectedItemId);

            actionUrl = runLotteryBtn.data('action-url') + '?' + urlParams.toString();

            showConfirmationModal({
                title: gettext('Confirm Lottery Run'),
                description: gettext('You are about to run the lottery for the following product:'),
                productName: selectedItemText,
                showProduct: true,
                warning: gettext('This action will shuffle the waiting list priorities for this product. This cannot be easily undone.'),
                confirmButtonText: gettext('Yes, run the lottery')
            });

            return false;
        });
    }

    if (revertListBtn.length && itemSelect.length) {
        revertListBtn.on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            var selectedItemId = itemSelect.val();
            var selectedItemText = itemSelect.find('option:selected').text();

            if (!selectedItemId || selectedItemId === '' || selectedItemId === null || selectedItemId === undefined) {
                alert(gettext('You must select a specific product to revert the list. Please select a product from the dropdown and try again.'));
                return false;
            }

            var urlParams = buildFilterParams();
            urlParams.set('item', selectedItemId);

            actionUrl = revertListBtn.data('action-url') + '?' + urlParams.toString();

            showConfirmationModal({
                title: gettext('Confirm List Reversion'),
                description: gettext('You are about to revert the waiting list priorities for the following product:'),
                productName: selectedItemText,
                showProduct: true,
                warning: gettext('This action will restore the waiting list priorities to their original order. This cannot be easily undone.'),
                confirmButtonText: gettext('Yes, revert the list')
            });

            return false;
        });
    }

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

    if (confirmBtn.length) {
        confirmBtn.on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            if (actionUrl) {
                confirmModal.modal('hide');
                $('.modal-backdrop').remove();
                $('body').removeClass('modal-open');
                $('body').css('padding-right', '');
                window.location.href = actionUrl;
            }
        });
    }
});
