FROM python:3.11-slim
RUN pip install grpcio grpcio-tools
WORKDIR /app
COPY hello.proto server.py client.py ./
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. hello.proto
