class ReadOnlyEmailMixin:
    """
    Locks the waiting-list email to the logged-in customer's address. The view pre-fills it from
    the customer, and Django ignores submitted values for disabled fields.

    Mixed into whatever form class the ``waitinglist_form_class`` chain provides; see
    ``waitinglist_form_with_readonly_email``.
    """

    def __init__(self, *args, **kwargs):
        customer = kwargs.get("customer")
        super().__init__(*args, **kwargs)
        if customer:
            self.fields["email"].disabled = True


def waitinglist_form_with_readonly_email(cls):
    return type("WaitingListFormWithReadOnlyEmail", (ReadOnlyEmailMixin, cls), {})
