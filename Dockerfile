FROM python:alpine
WORKDIR /src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src /src
RUN adduser -D -u 1000 kopf
USER 1000
ENTRYPOINT [ "kopf", "run", "/src/controller.py"]
CMD [ "-A" , "-L", "http://0.0.0.0:8080"]