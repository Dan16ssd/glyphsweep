# Disposable browser sandbox. Built once, run once per job, destroyed after.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

RUN apt-get update  && apt-get install -y --no-install-recommends       fonts-noto-core fonts-dejavu-core fonts-liberation       tesseract-ocr tesseract-ocr-lao tesseract-ocr-tha tesseract-ocr-khm tesseract-ocr-mya  && rm -rf /var/lib/apt/lists/*  && pip install --no-cache-dir pillow==10.4.0 playwright==1.48.0  && fc-cache -f

# "Bare device" profile: Latin-only fonts (Liberation), no Lao/Thai/Khmer/Myanmar system font.
COPY bare-fonts.conf /opt/glyphsweep/bare-fonts.conf
COPY runner.py checks.js /opt/glyphsweep/
# Fail the build if the bare profile can still render any target script.
RUN for l in lo th km my; do       n=$(FONTCONFIG_FILE=/opt/glyphsweep/bare-fonts.conf fc-list :lang=$l | wc -l);       [ "$n" = 0 ] || { echo "bare profile still has fonts for $l"; exit 1; };     done

ENV HOME=/tmp XDG_CACHE_HOME=/tmp/.cache PYTHONDONTWRITEBYTECODE=1
USER pwuser
WORKDIR /tmp
ENTRYPOINT ["python3", "/opt/glyphsweep/runner.py"]
