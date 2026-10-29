Sideburn Core
=============

This is a plugin for `pretix`_.

Sideburn customizations that don't belong to the lottery or Twilio plugins:
login-required storefront, read-only waiting-list email, the Burning Man Project
regional event disclaimer on the event front page, Sideburn-specific copy, and
waiting-list operations (waiting-list vouchers bypass the quota, no signing
up again while holding a live voucher, and an admin "Delete selected" that also
deletes entries with vouchers).

Enable it per event in the 'plugins' tab of the event settings.

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Activate the virtual environment you use for pretix development.

3. Execute ``pip install -e .`` within this directory to register this
   application with pretix's plugin registry.

4. Restart your local pretix server.

Run the tests from the monorepo's ``src`` directory::

    pytest ../pretix-sideburn-core/tests

License
-------

Copyright 2026 Ryan

Released under the terms of the Apache License 2.0


.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
