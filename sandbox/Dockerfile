# Disposable browser sandbox. Built once, run once per job, destroyed after.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      fonts-noto-core fonts-dejavu-core \
      tesseract-ocr tesseract-ocr-lao tesseract-ocr-tha tesseract-ocr-khm tesseract-ocr-mya \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pillow==10.4.0 \
 && fc-cache -f

# "Bare device" profile: Latin-only fonts, no Lao/Thai/Khmer/Myanmar system font.
COPY bare-fonts.conf /opt/glyphsweep/bare-fonts.conf
COPY runner.py checks.js /opt/glyphsweep/

ENV HOME=/tmp XDG_CACHE_HOME=/tmp/.cache PYTHONDONTWRITEBYTECODE=1
USER pwuser
WORKDIR /tmp
ENTRYPOINT ["python3", "/opt/glyphsweep/runner.py"]
