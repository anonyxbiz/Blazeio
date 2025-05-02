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
async def request(self):
    """Generator for incoming data chunks"""
    while True:
        await self.ensure_reading()
        while self.__stream__:
            yield bytes(self.__buff__memory__[:self.__stream__.popleft()])
```

### Advanced Features

#### Chunked Encoding
```python
async def write_chunked(self, data):
    """HTTP chunked transfer encoding"""
    await self.writer(b"%X\r\n%s\r\n" % (len(data), data))

async def handle_chunked(self):
    """Parse incoming chunked data"""
    async for chunk in self.ayield():
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
    - `init()`: Initializes the application and sets up the event loop.
    - `add_route()`: Adds routes dynamically.
    - `serve_route()`: Handles incoming requests and routes them to the appropriate handler.
    - `run()`: Starts the server, listens for connections, and handles requests.
    - `exit()`: Gracefully shuts down the server.

### Middleware

Blazeio includes various middlewares that provide hooks into the request/response lifecycle:

- **before_middleware**: Executes before the target route is processed, ideal for logging or preparation tasks.
- **handle_all_middleware**: Executes when no specific route is matched, instead of returning a 404 error.
- **after_middleware**: Executes after the target route has been processed, for cleanup tasks or logging.

### Request Module

The **Request** module provides utilities to work with incoming HTTP requests:

- **get_json**: Parses JSON data from the request.
- **get_form_data**: Parses multipart form data into a structured JSON object.
- **get_params**: Retrieves URL parameters from the request.
- **get_upload**: Handles file uploads by streaming the file data in chunks.

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
    raise Abort("Route not found, but handled.", 404)
```

---

## Tools & Request Utilities

Blazeio includes several useful tools to make handling requests easier:

### Request Tools

- **Request.get_json**: Retrieve JSON data from the request body:
    ```python
    json_data = await Blazeio.Request.get_json(r)
    ```

- **Request.get_form_data**: Retrieve form data, including file upload form data:
    ```python
    form_data = await Blazeio.Request.get_form_data(r)
    ```

- **Request.get_upload**: Stream file uploads in chunks:
    ```python
    async for chunk in Blazeio.Request.get_upload(r):
        # Process file chunk
    ```

---

# Blazeio Quick Start Guide

## Requirements
Python 3.7+, aiologger, aiofiles.

```bash
pip install Blazeio
```

## Example Application

This example demonstrates both Object-Oriented Programming (OOP) and Functional Programming (FP) approaches to define routes and middleware.

### Full Example Code

```python
import Blazeio as io
from asyncio import new_event_loop
from os import path

web = io.App("0.0.0.0", 8000)

# OOP IMPLEMENTATION
class Server:
    @classmethod
    async def setup(app):
        app = app()
        """
            Automatically registers VALID API ENDPOINTS methods to the app.
            VALID API ENDPOINTS here are those that start with _ but not __, then _ will be replaced with / when adding them to the registry.
        """
        await web.append_class_routes(app)

        app.static = await io.IN_MEMORY_STATIC_CACHE.init(
            run_time_cache={
                "/page/index.html": {"route": "/"}
            },
            chunk_size=1024,
            home_dir=path.abspath(path.dirname(__file__))
        )

        return app

    async def before_middleware(app, r):
        r.store = {"json_data": = await io.Request.body_or_params(r)}

    # /
    async def _redirect(app, r):
        # Redirect users to the IP endpoint
        await io.Deliver.redirect(r, "/api/ip")

    # handle undefined endpoints and serve static files
    async def handle_all_middleware(app, r):
        await app.static.handler(r, override="/page/index.html")  # Will override for / path.

    # /api/ip/
    async def _api_ip(app, r):
        data = {
            "ip": str(r.ip_host) + str(r.ip_port)
        }

        await io.Deliver.json(r, data)


# FP Implementation
@web.add_route
async def this_function_name_wont_be_used_as_the_route_if_overriden_in_the_route_param(r, route="/fp"):
    message = "Hello from some functional endpoint"

    # Send a text response
    await io.Deliver.text(r, message)

if __name__ == "__main__":
    io.loop.run_until_complete(Server.setup())
    web.runner()
```

### Explanation

1. **Object-Oriented Programming (OOP) Approach:**
   - `Server` class sets up the application, handles static files, and defines routes.
   - The `setup` method initializes the app, registers routes, and prepares the static file handler.
   - Custom middleware is added for request handling (`before_middleware`) and for serving static files or redirecting (`handle_all_middleware`).

2. **Functional Programming (FP) Approach:**
   - The `@web.add_route` decorator is used to define functional endpoints. The `this_function_name_wont_be_used_as_the_route_if_overriden_in_the_route_param` function handles the `/fp` route.

3. **Middleware and Request Handling:**
   - The `before_middleware` method ensures that incoming requests have the necessary JSON or form data parsed and stored in `r.json_data`.
   - The `handle_all_middleware` method serves static files and handles undefined routes by redirecting them or serving the default HTML page.

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
    await io.Deliver.text(r, "This is /new/route")
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
   - Timeout cascades cancel stuck operations

## Example Use Cases

### Reverse Proxy
```python
async def proxy_handler(r):
    async with io.Session(upstream_url) as resp:
        await r.prepare(resp.headers, resp.status_code)
        async for chunk in resp.pull():
            await r.write(chunk)
```

### Real-Time Streaming
```python
async def sse_handler(r):
    while True:
        await r.write(f"data: {timestamp()}\n\n")
        await asyncio.sleep(1)
```

### File Upload with Validation
```python
async def upload_handler(r):
    form = await io.Request.form_data(r)
    if not validate(form.get("metadata")):
        raise io.Abort("Invalid metadata", 400)

    async for chunk in r.pull():
        await storage.write(chunk)
```

---

## Contributing

If you would like to contribute to Blazeio, feel free to fork the repository and submit a pull request. Bug reports and feature requests are also welcome!

---

## License

Blazeio is open-source and licensed under the MIT License.

---
