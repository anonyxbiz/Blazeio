## Overview

**Blazeio** is a cutting-edge asynchronous web server and client framework designed for building high-performance backend applications with minimal overhead.

Built on Python's asyncio event loop, Blazeio provides:

- Zero-copy streaming
- Protocol-agnostic request handling
- Automatic backpressure management
- Microsecond-level reactivity
- Connection-aware processing

Blazeio operates at the transport layer while maintaining a simple, developer-friendly API.

## Key Features

- 🚀 **Event-optimized I/O**: Direct socket control with smart backpressure
- ⚡ **Instant disconnect detection**: No zombie connections
- 🔄 **Bidirectional streaming**: HTTP/1.1, SSE, and custom protocols
- 🧠 **Memory-safe architecture**: No buffer overflows
- ⏱️ **Precise flow control**: Async sleeps instead of spinlocks
- 🔗 **Unified client/server API**: Same code for both sides

## Core API: Request Object

### `BlazeioServerProtocol` (Request Object)

The foundation of Blazeio's performance comes from its optimized request handling:

```python
class BlazeioServerProtocol(BufferedProtocol, BlazeioPayloadUtils, ExtraToolset):
    __slots__ = (
        'transport', 'method', 'path', 'headers',
        'content_length', 'current_length', 'transfer_encoding'
        # ... and other internal state
    )
```

### Essential Methods

#### Connection Management
```python
def connection_made(self, transport):
    """Called when new client connects"""
    self.transport = transport

def connection_lost(self, exc):
    """Called when client disconnects"""
    self.__is_alive__ = False

def abort_connection(self):
    """Called when the connection is half-opened"""

```

#### Flow Control
```python
async def buffer_overflow_manager(self):
    """Sleeps at 0% CPU when kernel buffers are full"""
    if self.__is_buffer_over_high_watermark__:
        await self.__overflow_evt__.wait()
        self.__overflow_evt__.clear()

async def writer(self, data: bytes):
    """Safe write with backpressure and disconnect checks"""
    await self.buffer_overflow_manager()
    if not self.transport.is_closing():
        self.transport.write(data)
```

#### Streaming
```python
async def __aiter__(self):
    """Generator for incoming data chunks"""
    while True:
        await self.ensure_reading()
        while self.__stream__:
            yield self.__stream__.popleft()
```

### Advanced Features

#### Chunked Encoding
```python
async def write_chunked(self, data):
    """HTTP chunked transfer encoding"""
    await self.writer(b"%X\r\n%s\r\n" % (len(data), data))

async def handle_chunked(self):
    """Parse incoming chunked data"""
    async for chunk in self:
        yield chunk  # Auto-decodes chunked encoding
```

#### Compression
```python
async def br(self, data: bytes):
    """Brotli compression"""
    return await to_thread(brotlicffi_compress, data)

async def gzip(self, data: bytes):
    """Gzip compression"""
    encoder = compressobj(wbits=31)
    return encoder.compress(data) + encoder.flush()
```

## Modules

Blazeio consists of several modules that each serve a specific purpose. Below is a breakdown of the main modules included:

### Core Module

- **App**: The core app class that handles the event loop, server setup, and route management.
    - `__init__()`: Initializes the application.
    - `add_route()`: Adds routes dynamically.
    - `handle_client()`: Handles incoming requests and routes them to the appropriate handler.
    - `runner()`: Starts the server, listens for connections, and handles requests.
    - `exit()`: Gracefully shuts down the server.

### Middleware

Blazeio includes various middlewares that provide hooks into the request/response lifecycle:

- **before_middleware**: Executes before the target route is processed, ideal for logging or preparation tasks.
- **handle_all_middleware**: Executes when no specific route is matched, instead of returning a 404 error.
- **after_middleware**: Executes after the target route has been processed, for cleanup tasks or logging.

### Request Module

The **Request** module provides utilities to work with incoming HTTP requests:

- **get_json**: Parses JSON data from the request.
- **params**: Retrieves URL parameters from the request.
- **pull**: Streams the incoming data in chunks for the parsed protocol.
- **__aiter__**: Streams the raw incoming data in chunks without protocol deserialization.

### Streaming

- **Deliver**: Manages data delivery and ensures that responses are properly handled.
- **Abort**: An exception used to quickly abort a request.

### Static File Handling

- **Simpleserve**: Serves files directly from the server. This module is ideal for applications that require fast delivery of static content, such as websites serving assets like HTML, CSS, and JavaScript files, especially when theyre small files that are frequently accessed.

## Middleware Usage

Blazeio’s middleware system allows you to hook into various stages of request processing.

### Example of `before_middleware`

This middleware runs before the actual route handler is executed:

```python
@web.add_route
async def before_middleware(request):
    # Perform some task before the route is executed
    print("Before route executed.")
```

### Example of `after_middleware`

This middleware runs after the route handler finishes:

```python
@web.add_route
async def after_middleware(request):
    # Perform some task after the route is executed
    print("After route executed.")
```

### Example of `handle_all_middleware`

This middleware runs when no specific route is matched, avoiding a default 404 response:

```python
@web.add_route
async def handle_all_middleware(request):
    raise Blazeio.Abort("Route not found, but handled.", 404)
```

---

## Tools & Request Utilities

Blazeio includes several useful tools to make handling requests easier:

### Request Tools

- **.get_json**: Retrieve JSON data from the request body:
    ```python
    json_data = await request.get_json()
    ```

- **.form_data**: Retrieve form data, including file upload form data:
    ```python
    form_data = await request.form_data(r)
    ```

- **.pull**: Stream file uploads in chunks:
    ```python
    async for chunk in request.pull():
        ...
        # Process file chunk
    ```

---

# Blazeio Quick Start Guide

## Requirements
Python 3.7+, psutil, aiofile, brotlicffi, xmltodict.

```bash
pip install blazeio
```

## Example Application

This example demonstrates both Object-Oriented Programming (OOP) and Functional Programming (FP) approaches to define routes and middleware.

### Full Example Code

```python
import Blazeio as io

web = io.App("0.0.0.0", 8000, with_keepalive = 1)

web.attach(io.StaticServer("/", io.path.join(io.getcwd(), "static"), 1024*100, "page", "index.html"))

# OOP IMPLEMENTATION
@web.attach
class Server:
    def __init__(app):
        ...

    async def before_middleware(app, r):
        r.store = {"json_data": await r.body_or_params()}

    # /
    async def _redirect(app, r):
        # Redirect users to the IP endpoint
        raise io.Abort("", 302, io.ddict(location = "/api/ip"))

    # handle undefined endpoints and serve static files
    async def handle_all_middleware(app, r):
        raise io.Abort("Not Found", 404)

    # /api/ip/
    async def _api_ip(app, r):
        data = {
            "ip": str(r.ip_host) + str(r.ip_port)
        }

        await io.Deliver.json(data)

# FP Implementation
@web.add_route
async def this_function_name_wont_be_used_as_the_route_if_overriden_in_the_route_param(r, route="/fp"):
    # Send a text response
    await io.Deliver.text("Hello from some functional endpoint")

if __name__ == "__main__":
    with web:
        web.runner()
```

### Explanation

1. **Object-Oriented Programming (OOP) Approach:**
   - `Server` class sets up the application defining routes from methods.
   - Custom middleware is added for request handling (`before_middleware`) and for handling undefined routes (`handle_all_middleware`).

2. **Functional Programming (FP) Approach:**
   - The `@web.add_route` decorator is used to define functional endpoints. The `this_function_name_wont_be_used_as_the_route_if_overriden_in_the_route_param` function handles the `/fp` route.

3. **Middleware and Request Handling:**
   - The `before_middleware` method ensures that incoming requests have the necessary JSON or form data parsed and stored in `r.json_data`.
   - The `handle_all_middleware` metho handles undefined routes.

### Running the App

1. Create a Python file (e.g., `app.py`) and paste the example code above.
2. Run the app with:

```bash
python app.py
```

3. Open your browser and visit `http://localhost:8000` to view the app. You should see a static page, visit `http://localhost:8000/redirect` and it will redirect to `/api/ip`, which returns your IP.

### Customizing Routes

- To add more routes, simply create new methods starting with `_` inside the `Server` class. The method name (with `_` replaced by `/`) will be automatically mapped to the corresponding route.

Example:
```python
async def _new_route(app, r):
    await io.Deliver.text("This is /new/route")
```

This will automatically add a new route at `/new/route`.

## Why Blazeio?

1. **Zero-Copy Architecture**
   - No unnecessary data copies between kernel and userspace
   - Memory views instead of byte duplication

2. **Microsecond-Level Reactivity**
   - Small chunk sizes (default 4KB) enable rapid feedback
   - Immediate disconnect detection

3. **Self-Healing Design**
   - Automatic cleanup of dead connections

## Example Use Cases

### Blazeio WebRTC-like Signaling Server Example
```python
"""
Blazeio WebRTC-like Signaling Server Example

This example demonstrates a peer-to-peer signaling server that allows clients
to create "rooms" and establish direct connections through chunked transfer encoding.
It includes built-in performance testing capabilities.
"""

import Blazeio as io
import Blazeio.Other.class_parser as class_parser
import Blazeio.Other.crypto as crypto  # Blazeio XOR cipher for room encryption

# Initialize web server with keepalive support
web = io.App("0.0.0.0", 3002, with_keepalive=1)

# Configure chunk sizes for optimal streaming performance
io.INBOUND_CHUNK_SIZE, io.OUTBOUND_CHUNK_SIZE = 1024 * 100, 1024 * 100

# Global database for room management and crypto operations
db = io.ddict(
    rooms=io.ddict(),  # Active rooms storage
    cipher=crypto.Ciphen(io.environ.get("hash", io.token_urlsafe(11)))  # XOR cipher for room ID encryption
)


class User:
    """
    Represents a user connection in a peer-to-peer room.
    
    Manages connection state, data streaming, and peer synchronization.
    """
    
    __slots__ = ("room", "wake_up", "r", "on_close", "remote")
    
    def __init__(app, r, room):
        """
        Initialize a user connection.
        
        Args:
            r: Request protocol object
            room: Room identifier or remote user object
        """
        app.room = room
        app.r = r  # Request protocol
        app.wake_up = io.SharpEvent()  # Event to signal peer connection
        app.on_close = io.SharpEvent()  # Event to signal connection closure
        app.remote = None  # Reference to connected peer

        # Register in rooms database if this is the first user
        if not isinstance(app.room, User):
            db.rooms[app.room] = app
        else:
            # Connect two users as peers
            app.room.remote, app.remote = app, app.room
            app.remote.wake_up.set()  # Notify the waiting peer

    def __await__(app):
        """Allow awaiting for peer connection."""
        _ = yield from app.wake_up.wait_clear().__await__()
        return _

    def clean(app):
        """Clean up room registration when user disconnects."""
        if app.room in db.rooms:
            db.rooms.pop(app.room)
        app.on_close.set()

    def __aiter__(app):
        """Make user iterable for streaming data from remote peer."""
        return app.remote.r.pull()

    async def __aenter__(app):
        """Context manager entry."""
        return app

    async def __aexit__(app, *args):
        """Context manager exit - cleanup resources."""
        await app.r.eof()  # End of file for the connection
        app.on_close.set()
        
        # Only clean room if this was the room creator
        if not isinstance(app.room, User):
            app.clean()
        return False


@web.attach
class Server:
    """
    Main server class handling room creation and joining operations.
    """
    
    __slots__ = ()
    
    def __init__(app):
        """Server initialization."""
        ...

    async def _app_room_create(app, r: io.BlazeioProtocol):
        """
        Create a new room and wait for a peer to join.
        
        Args:
            r: Request protocol object
        """
        # Generate encrypted room ID from client IP:port
        client_identifier = f"{r.ip_host}:{int(r.ip_port)}".encode()
        encrypted_id = db.cipher.encrypt(client_identifier)
        room = io.urlsafe_b64encode(encrypted_id).decode()

        await io.plog.cyan(f"{r.method} @ {r.tail}", room)

        # Create user context for room management
        async with User(r, room) as user:
            # Send immediate response headers with room ID
            await r.prepare({
                "Content-type": r.headers.get("Content-type"),
                "room": user.room,
                **io.Ctypes.chunked
            }, 200)

            # Wait for a peer to join the room
            await user

            # Stream data from peer to this client
            async for chunk in user:
                await r.write(chunk)

    async def _app_room_join(app, r: io.BlazeioProtocol):
        """
        Join an existing room and connect to the room creator.
        
        Args:
            r: Request protocol object
            
        Raises:
            io.Abort: If room is invalid or not found
        """
        # Validate room parameter
        if not (room_id := r.params().get("room")):
            raise io.Abort("room parameter is required!", 403)

        # Check if room exists
        if not (room := db.rooms.get(room_id)):
            raise io.Abort("room not found", 404)

        # Join the room as peer
        async with User(r, room) as user:
            # Send response headers
            await r.prepare({
                "Content-type": r.headers.get("Content-type"),
                "room": user.room,
                **io.Ctypes.chunked
            }, 200)

            # Stream data from peer to this client
            async for chunk in user:
                await r.write(chunk)
                

class Main:
    """
    Performance testing client for the signaling server.
    
    Creates multiple client pairs to test room creation and data transfer performance.
    """
    
    __slots__ = ("payload_size", "chunk_range", "concurrency", "test", "payload")
    task_serializer = io.SharpEvent()  # Synchronize task startup
    headers = {
        "Content-type": "text/plain",
        "Transfer-encoding": "chunked"
    }
    
    def __init__(app, 
                 payload_size: (int, io.Utype) = 1024 * 100,
                 chunk_range: (int, io.Utype) = 100,
                 concurrency: (int, io.Utype) = 10,
                 test: (int, io.Utype, class_parser.Store) = 0):
        """
        Initialize performance test parameters.
        
        Args:
            payload_size: Size of each data chunk in bytes
            chunk_range: Number of chunks to send per connection
            concurrency: Number of concurrent client pairs to test
            test: Whether to run performance tests
        """
        io.set_from_args(app, locals(), (io.Utype, io.Unone))
        app.payload = b"." * app.payload_size  # Test payload data
        
        # Start performance test runner if testing is enabled
        if app.test:
            io.create_task(app.runner())

    async def runner(app):
        """
        Main test runner - creates client pairs and measures performance.
        """
        await web  # Wait for server to start
        
        async with io.Ehandler(ignore=io.CancelledError):
            # Create concurrent client tasks
            tasks = [io.create_task(app.client_create()) for _ in range(app.concurrency)]
            app.task_serializer.set()  # Release all tasks simultaneously

            # Wait for all tests to complete
            results = await io.gather(*tasks)
            await io.plog.green("Performance test completed", io.dumps(results))

        await web.exit()  # Shutdown server after tests

    async def client_create(app):
        """
        Create a room and act as the first peer in the connection.
        
        Returns:
            Performance analysis data
        """
        await app.task_serializer.wait()  # Wait for synchronization

        async with io.getSession.post(
            web.server_address + "/app/room/create",
            app.headers
        ) as resp:
            await resp.prepare_http()  # Receive response headers

            # Start the joining peer in parallel
            join_task = io.create_task(app.client_join(resp.headers.room))
            
            # Initialize performance tracking
            analysis = io.ddict(
                duration=io.perf_timing(),  # Performance timer
                bytes_transferred=0,
                room=resp.headers.room
            )

            # Receive data from the joining peer
            async for chunk in resp:
                analysis.bytes_transferred += len(chunk)

            # Calculate performance metrics
            analysis.duration = analysis.duration().elapsed
            analysis.mb_transferred = float(analysis.bytes_transferred / (1024 ** 2))
            analysis.transfer_rate = float(analysis.mb_transferred / analysis.duration) if analysis.duration > 0 else 0

            # Send final performance data
            performance_data = {
                "duration": analysis.duration,
                "bytes_transferred": analysis.bytes_transferred,
                "room": analysis.room,
                "mb_transferred": analysis.mb_transferred,
                "transfer_rate": analysis.transfer_rate
            }
            await resp.eof(io.dumps(performance_data).encode())

            return await join_task

    async def client_join(app, room: str):
        """
        Join an existing room and send test data.
        
        Args:
            room: Room identifier to join
            
        Returns:
            Response data from the room creator
        """
        async with io.getSession.post(
            web.server_address + "/app/room/join",
            app.headers,
            params=io.ddict(room=room)
        ) as resp:
            # Send test payload in chunks
            for i in range(app.chunk_range):
                await resp.write(app.payload)

            await resp.eof()  # Signal end of data

            return await resp.json()

if __name__ == "__main__":
    """
    Main entry point with command-line argument parsing.
    """
    # Parse command line arguments
    args = class_parser.Parser(Main, io.Utype).args()

    # Initialize main application with parsed arguments
    main_app = Main(**args)

    # Start the web server
    with web:
        web.runner()
```

### Server To Server Streaming
```python
"""
This example demonstrates how to upload files from a URL directly to AWS S3 using Blazeio's built-in AWS S3 module for authenticated request signing.
"""

import Blazeio as io
import Blazeio.Other.aws_s3 as aws_s3  # Import Blazeio AWS S3 module for authenticated requests

# Enable line number tracking in Blazeio logger for better debugging
io.plog.track_lineno = True

# AWS S3 Configuration - supports both environment variables and hardcoded values
if (aws_s3_config := io.environ.get("aws_s3_config", None)):
    # Load configuration from environment variable if available
    aws_s3_config = io.ddict(io.loads(aws_s3_config))
else:
    # Fallback to hardcoded configuration (use environment variables in production)
    aws_s3_config = io.ddict(
        aws_bucket="your-bucket-name",
        aws_region="us-east-1", 
        aws_key="your-access-key",
        aws_secret="your-secret-key"
    )

# Initialize the Blazeio AWS S3 module for signing authenticated requests
s3 = aws_s3.S3(
    aws_s3_config.aws_bucket, 
    aws_s3_config.aws_region, 
    aws_s3_config.aws_key, 
    aws_s3_config.aws_secret
)

class Main:
    """Main application class handling file uploads to AWS S3"""
    
    __slots__ = ("root",)  # Memory optimization
    
    def __init__(app, root: str):
        """
        Initialize the application
        
        Args:
            root: Root directory path in S3 bucket where files will be uploaded
        """
        io.set_from_args(app, locals(), (str,))  # Set and validate argument types
        
    async def main(app, *args, **kwargs):
        """
        Main entry point wrapped in exception handler
        
        Returns:
            Result of the upload operation
        """
        async with io.Ehandler():  # Automatic exception logging and handling
            return await app.upload(*args, **kwargs)
            
    async def upload(app, url: str):
        """
        Upload a file from URL directly to AWS S3
        
        Args:
            url: Source URL of the file to upload
            
        Raises:
            io.Err: If file metadata extraction fails or file is invalid
        """
        # Step 1: Extract file metadata from source URL
        await io.plog.blue("Extracting file metadata from source URL...")
        
        async with io.getSession.head(
            url, 
            io.Rvtools.headers, 
            follow_redirects=True
        ) as file:
            if not file.ok():
                raise io.Err(f"Failed to extract file metadata: Status {file.status_code}, Reason: {file.reason_phrase}")
            if not file.content_length:
                raise io.Err("File must have the Content-Length HTTP header")
                
        # Extract filename from URL or headers
        filename = file.get_filename() or io.path.basename(file.path)
        
        await io.plog.cyan("File metadata extracted successfully", io.ddict(
            filename=filename,
            content_type=file.content_type,
            content_length=file.content_length,
            source_url=url
        ))

        # Step 2: Prepare S3 upload with authenticated request
        s3_object_path = f"{app.root}/{io.Request.url_encode(filename)}"
        
        await io.plog.magenta("Preparing S3 upload with authenticated request...")
        
        async with io.getSession(
            **s3.authorize(s3_object_path, {
                "content-type": file.content_type,
                "content-length": file.content_length,
                "content-disposition": f'{"inline" if file.content_type != "application/octet-stream" else "attachment"}; filename="{io.Request.url_encode(filename)}"',
            })
        ) as uploader, io.getSession.get(url, io.Rvtools.headers) as file_stream:
            
            # Log upload initialization
            await io.plog.yellow("Starting file upload to S3", io.anydumps(io.ddict(
                filename=filename,
                s3_path=uploader.path,
                target_bucket=aws_s3_config.aws_bucket
            ), indent=2))

            # Step 3: Stream file from source to S3 with progress tracking
            start_time = io.perf_counter()
            transferred_data = 0
            
            await io.plog.blue("Streaming file data to AWS S3...")

            # Disable line tracking during upload to reduce log noise
            io.plog.track_lineno = False

            async for chunk in file_stream:
                # Write chunk to S3
                await uploader.write(chunk)
                transferred_data += len(chunk)
                
                # Calculate and log progress
                progress_percent = (file_stream.received_len / file_stream.content_length) * 100
                elapsed_time = io.perf_counter() - start_time
                transfer_rate = (transferred_data / (1024 ** 2)) / elapsed_time if elapsed_time > 0 else 0
                
                await io.plog.yellow(
                    f"<line_{io.plog.lineno}>",
                    "Upload Progress", 
                    f"Progress: {progress_percent:.2f}%",
                    f"Transfer Rate: {transfer_rate:.2f} MB/s"
                )

            # Step 4: Finalize the upload
            await io.plog.green("Finalizing upload...")
            await uploader.prepare_http()

            # Log upload completion details
            await io.plog.green("Upload completed successfully!", io.anydumps(io.ddict(
                status_code=uploader.status_code,
                reason=uploader.reason_phrase,
                headers=dict(uploader.headers),
                response_data=await uploader.text()
            ), indent=2))

            # Step 5: Verify the uploaded file by making a HEAD request
            await io.plog.blue("Verifying uploaded file...")
            
            async with io.getSession.head(s3.url(uploader.path), io.Rvtools.headers) as verification:
                await io.plog.green("File verification completed", io.anydumps(io.ddict(
                    status_code=verification.status_code,
                    reason=verification.reason_phrase,
                    headers=dict(verification.headers),
                    verification_data=await verification.text()
                ), indent=2))


if __name__ == "__main__":
    """
    Example usage: Upload a sample video file to S3
    """
    # Initialize the application with S3 path and start the upload
    io.ioConf.run(
        Main("/app/files/uploads").main(
            "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        )
    )
```

---

## Contributing

If you would like to contribute to Blazeio, feel free to fork the repository and submit a pull request. Bug reports and feature requests are also welcome!

---

## License

Blazeio is open-source and licensed under the MIT License.

---