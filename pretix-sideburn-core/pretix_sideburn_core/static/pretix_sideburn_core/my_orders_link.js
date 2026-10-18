/* Puts the "My Orders" link in front of the customer's name in the storefront header. */
(function () {
    var template = document.getElementById("sideburn-my-orders-link");
    if (!template) {
        return;
    }
    document.querySelectorAll("nav.loginstatus").forEach(function (nav) {
        nav.insertBefore(template.content.cloneNode(true), nav.firstChild);
    });
})();
