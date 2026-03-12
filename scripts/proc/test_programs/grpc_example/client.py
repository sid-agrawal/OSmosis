import grpc
import time
import sys
import hello_pb2
import hello_pb2_grpc


chan = grpc.insecure_channel(f'{sys.argv[1]}:50051')
stub = hello_pb2_grpc.GreeterStub(chan)
print(f"gRPC client connecting to {sys.argv[1]}:50051", flush=True)
while True:
    try:
        r = stub.SayHello(hello_pb2.HelloRequest(name='world'))
        print(f"Response: {r.message}", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)
    time.sleep(5)
