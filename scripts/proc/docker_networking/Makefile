all: binary image

binary:
	gcc -static nw_client.c -o bin_nw_client
	gcc -static nw_server.c -o bin_nw_server

image:
	docker build -t server-osm-ubuntu -f server_Dockerfile .
	docker build -t client-osm-ubuntu -f client_Dockerfile .

clean:
	rm bin_nw_client bin_nw_server
	docker rmi server-osm-ubuntu
	docker rmi client-osm-ubuntu
