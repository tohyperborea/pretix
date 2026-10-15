FROM pretix/standalone:stable
USER root

ENV LC_ALL=C.UTF-8 \
    DJANGO_SETTINGS_MODULE=production_settings

COPY pretix-sideburn-twilio /pretix/pretix-sideburn-twilio
COPY pretix-sideburn-lottery /pretix/pretix-sideburn-lottery

RUN pip3 install -e /pretix/pretix-sideburn-twilio && \
    pip3 install -e /pretix/pretix-sideburn-lottery && \
    pip3 install -U "https://github.com/pretix-unofficial/pretix-regex-validation.git" && \
    pip3 install -U "https://github.com/pretix/pretix-passbook.git"


RUN cd /pretix/src && \
    make production
USER pretixuser
