This is based on [1] and [2]

```bash
docker network create osmosis
make # Build binaries and container images
```

Start two containers connected to the docker osmosis network.

C1: Server
```bash
host> docker run --rm -it --network osmosis --name dn-server server-osm-ubuntu bash
root@c723c3ca813d:/# /nw_server

[server is listening]

[After the client is run, you should see this]

Hello from client       valread:17
Hello message sent
```

C2: Client
```bash
host> docker run --rm -it --network osmosis --name dn-client client-osm-ubuntu bash
root@783df1abe137:/# nslookup dn-server
Server:         127.0.0.11
Address:        127.0.0.11#53

Non-authoritative answer:
Name:   dn-server
Address: 172.18.0.3

root@783df1abe137:/# ./nw_client 172.18.0.3
Hello message sent
Hello from server
valread: 17s
```









[1] https://www.geeksforgeeks.org/connecting-two-docker-containers-over-the-same-network/
[2] https://www.geeksforgeeks.org/socket-programming-cc/

