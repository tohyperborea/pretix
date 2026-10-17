FROM pretix/standalone:2026.8.0
USER root

ENV LC_ALL=C.UTF-8 \
    DJANGO_SETTINGS_MODULE=

COPY pretix-sideburn-twilio /pretix/pretix-sideburn-twilio
COPY pretix-sideburn-lottery /pretix/pretix-sideburn-lottery

RUN pip install -e /pretix/pretix-sideburn-twilio && \
    pip install -e /pretix/pretix-sideburn-lottery && \
    pip3 install -U "git+https://github.com/pretix/pretix-passbook.git@ab662f9614f69d6fe963735878b951f2ef4bd83c"


RUN cd /pretix/src && \
    make production
USER pretixuser
