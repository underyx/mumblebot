Bot for mumble which, for now, does nothing other than replying to youtube.com links in text chat with their title.

The code is awfully ugly and hacked together right now - I'll fix this over time.

Note: My version of this bot is not meant to be used for general purposes, I just push whatever I personally am using it for. Sorry!

Compile mumble.proto:
	protoc --python_out=. Mumble.proto
