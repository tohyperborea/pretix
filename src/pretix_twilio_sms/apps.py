#
# This file is part of pretix (Community Edition).
#
# Copyright (C) 2014-2020 Raphael Michel and contributors
# Copyright (C) 2020-2021 rami.io GmbH and contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation in version 3 of the License.
#
# ADDITIONAL TERMS APPLY: Pursuant to Section 7 of the GNU Affero General Public License, additional terms are
# applicable granting you additional permissions and placing additional restrictions on your usage of this software.
# Please refer to the pretix LICENSE file to obtain the full terms applicable to this work. If you did not receive
# this file, see <https://pretix.eu/about/en/license>.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along with this program.  If not, see
# <https://www.gnu.org/licenses/>.
#
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from pretix import __version__ as version


class TwilioSmsApp(AppConfig):
    """
    Twilio SMS integration plugin for pretix.
    """

    name = 'pretix_twilio_sms'
    verbose_name = _("Twilio SMS integration")

    class PretixPluginMeta:
        """
        Basic plugin metadata used by pretix to display and manage plugins.
        """

        # Human-readable plugin name shown in the UI
        name = _("Twilio SMS integration")

        # Plugin identifier / module path for entry point registration
        identifier = "pretix_twilio_sms"

        # Author/maintainer information
        author = _("Sideburn")

        # Category groups this as a feature plugin (not payment/shipping/etc.)
        category = "FEATURE"

        # Version will be kept in sync with the core pretix version
        version = version

        # Short description for the plugin list
        description = _(
            "Adds Twilio-based SMS notifications, including waitlist updates and customer SMS preferences."
        )

