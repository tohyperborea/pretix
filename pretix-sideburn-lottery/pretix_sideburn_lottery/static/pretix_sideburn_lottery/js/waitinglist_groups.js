$(function () {
    var $action = $("input[name=lottery_group_action]");
    if (!$action.length) {
        return;
    }
    var groupItems = String($action.first().attr("data-lottery-group-items") || "").split(",");
    var $itemvar = $("#id_itemvar");
    var $code = $("#id_lottery_group_code");

    function update() {
        var item = String($itemvar.val() || "").split("-")[0];
        var allowed = groupItems.indexOf(item) !== -1;
        $action.closest(".form-group").toggle(allowed);
        $code.closest(".form-group").toggle(allowed && $action.filter("[value=join]").is(":checked"));
    }

    $itemvar.on("change", update);
    $action.on("change", update);
    update();
});
