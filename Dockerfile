FROM pretix/standalone:stable
USER root

COPY pretix-sideburn-twilio /pretix/pretix-sideburn-twilio
COPY pretix-sideburn-lottery /pretix/pretix-sideburn-lottery

RUN
    pip3 install -e /pretix/pretix-sideburn-twilio && \
    pip3 install -e /pretix/pretix-sideburn-lottery && \
    pip3 install -U "https://github.com/pretix-unofficial/pretix-regex-validation.git" && \
    pip3 install -U "https://github.com/pretix/pretix-passbook.git"


RUN
    cd /pretix/src && \
    sudo -u pretixuser make production
USER pretixuser
