# Plan to renovate project
## 8/9/23
Stages of the software:

User declares file list with file hash
User awaits download requests
User searches for file - it gets searched through all other users' declared files
User downloads a file

Where is the metadata of the file stored? What if it has the same hash, but different filename / metadata? The metadata is stored in the file. The only thing not in the file to worry about is the filename. If two users have the same file but different filenames for that file, both filenames should be offered to the user - preferring the one similar to the user's search query or the user's search query if no filenames given.

What about the user's filetree then? Should it be emulated in the server's search results?

The client should be able to request a folder tree to download. When you download a file, you should see in what folder hierarchies it exists in, and allow requesting the depth of the filetree to download in relation to this file.

So no, not just name, but filetree too.

### What is saved between sessions?
- list of declared folders
- uploads/downloads in progress

### Declaring a folder
- all subfolders are included
- all file names preserved
- all files get hashed
- file hash directs to the file tree
- file hash can direct to more than one tree
- (a certain file tree is preferred if it's shared by more users - forming a concensus)

### Searching
- look for file based on name, extension, filetype using `file`, hash, folder-name
- if specific file, downloading will ask you to give it a name and offer ones
- if it's a folder, it'll simply download the whole subtree
- if it's a file, show the rest of the folder very briefly and grayed out n stuff
- also show how many seeders
- maybe searching always gives you filetree results. it shows you in which filetrees the file exists. it is always in a non-filetree with the hash or nice filename as the name.

### Downloading
- like soulseek, it just downloads a folder or a file and it shows speed
- you can limit download speed
- log all downloads in log file
- show progress
- considering the download is subdivided into chunks, should you use a file to represent a chunk or is there a neater way? ideally it would be sorted but efficiently.
- use tar

### Uploading
- can set upload limit and slots
- show progress
- logging


## 7/9/23
Update server to be as good as client.

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
