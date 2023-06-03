# Plan to renovate project

## Partitioning
This project has 4 parts:
1. Client-client protocol
2. Client
3. Server-client protocol
4. Server


### Client-client communication protocol
This abstracts the communication between clients. It allows clients to request file chunks from each other.

### Client
An interface that allows a user to share their files, search for files, and download. It looks like SoulseekQT.

### Server-client communication protocol
This abstracts the communication between the server and client, and allows the client to query files from the servers and update user lists.

### Server
The server that stores client information on clients and allows searching for files.



## The plan

Firstly the basic functionality will be created. The client will be able to download a s
