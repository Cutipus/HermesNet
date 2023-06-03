from curio import run, tcp_server
KILOBYTE = 1024

async def receive_message(client, addr):
    # responsible for retrieving a single request from a client
    print('Connection from', addr)
    msg = bytearray()
    while True:
        data = await client.recv(KILOBYTE)
        if not data:
            break
        msg += data
    print('Message received')
    response = await process_message(msg)
    await client.sendall(response)

async def process_message(msg: bytearray) -> bytes:
    # parses the message and returns a reply
    # this server should return the ip addresses and data ranges of clients for specific files
    # therefore, the msg should include info on the file in question
    # a client can find info on a speciic file
    # or retrieve a list of files via search
    # the client-tracker protocol should be implemented here
    # first the message is unwrapped from the communication protocol
    # it is then processed
    # lastly the response is wrapped in the communication protocol and returned
    if msg == b'ping':
        print("Ping received")
        return b"I'm awake!"

if __name__ == '__main__':
    run(tcp_server, '', 25000, receive_message)
