import grpc
import time
from concurrent import futures
import hello_pb2
import hello_pb2_grpc


class Greeter(hello_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        return hello_pb2.HelloReply(message=f'Hello {request.name}')


server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
hello_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
server.add_insecure_port('[::]:50051')
server.start()
print("gRPC server listening on :50051", flush=True)
while True:
    time.sleep(3600)
