FROM python:3.12-slim
COPY proxy.py /proxy.py
USER 65534:65534
EXPOSE 8888
CMD ["python", "-u", "/proxy.py"]
