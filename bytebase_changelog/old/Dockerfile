FROM python:3.12-slim
COPY ./app /app
WORKDIR /app
RUN pip3 install flask requests
CMD ["python3", "bytebase_app.py"]
