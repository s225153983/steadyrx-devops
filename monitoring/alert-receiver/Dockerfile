FROM python:3.12-slim
RUN useradd --uid 10001 receiver
WORKDIR /srv
COPY receiver.py .
USER receiver
EXPOSE 9095
CMD ["python", "receiver.py"]
