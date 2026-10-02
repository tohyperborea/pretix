from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")


class PluginApp(PluginConfig):
    default = True
    name = "pretix_sideburn_core"
    verbose_name = "Sideburn Core"

    class PretixPluginMeta:
        name = gettext_lazy("Sideburn Core")
        author = "Ryan"
        description = gettext_lazy(
            "Sideburn storefront customizations (login-required storefront, waiting-list form, copy)"
        )
        visible = True
        version = __version__
        category = "CUSTOMIZATION"
        compatibility = "pretix>=2.7.0"
        settings_links = []
        navigation_links = []

    def ready(self):
        from . import signals  # NOQA
