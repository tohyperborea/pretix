# Sideburn: not in upstream pretix. Lets plugins replace the sold-out label through the
# sold_out_availability signal (used by pretix-sideburn-lottery). Returns an empty string when no
# plugin responds, so templates fall back to upstream's markup.
from django import template
from django.utils.html import conditional_escape

from pretix.presale.signals import sold_out_availability

register = template.Library()


@register.simple_tag(takes_context=True)
def sold_out_override(context, event, item, var=None, compact=False):
    for receiver, response in sold_out_availability.send(
        event,
        item=item,
        variation=var or None,
        allow_waitinglist=context.get("allow_waitinglist", False),
        cart_namespace=context.get("cart_namespace"),
        subevent=context.get("subevent"),
        compact=compact,
    ):
        if response:
            return conditional_escape(response)
    return ""
