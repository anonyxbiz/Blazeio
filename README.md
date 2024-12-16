## Overview

**Blazeio** is an ultra-fast asynchronous web framework crafted for high-performance backend applications. Built on Python's asyncio, it delivers non-blocking operations, minimal overhead, and lightning-quick request handling.

Designed with flexibility, low-latency operations, and simplicity in mind, Blazeio is perfect for developers aiming to create scalable, high-performing backend systems. Its asynchronous nature ensures top-tier performance with, while its modular structure allows easy customization and extension to meet any project's needs.

Blazeio offers a lean yet powerful foundation for building fast, scalable web applications. Whether you're using object-oriented or functional programming styles, Blazeio's intuitive setup and minimal boilerplate empower you to get your web app up and running quickly, while maintaining flexibility for complex use cases.

---

## Features

- **Asynchronous Execution**: Blazeio uses asyncio, ensuring that operations are non-blocking and allowing for high throughput, making it suitable for real-time applications.
- **Middleware System**: Blazeio supports powerful middleware that can run before, after, or in response to unmatched routes.
- **Request Handling**: Blazeio provides tools to easily manage and process incoming HTTP requests, including multipart form data and file uploads.
- **Route Management**: Dynamically add routes and middleware with minimal boilerplate.
- **Logging**: A custom logging system to track every action and request that passes through the server.
- **Streaming Support**: Efficient file and data streaming capabilities, optimized for large data transfers.
- **Static File Handling**: Built-in support for serving static files with the **IN_MEMORY_STATIC_CACHE**, enabling fast access to cached and compressed static resources directly from memory, improving performance for frequently accessed files.

---

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

- **stream_chunks**: A controlled way to stream request chunks, reducing memory overhead.
- **get_json**: Parses JSON data from the request.
- **get_form_data**: Parses multipart form data into a structured JSON object.
- **get_params**: Retrieves URL parameters from the request.
- **get_upload**: Handles file uploads by streaming the file data in chunks.

### Streaming

- **Stream**: Facilitates real-time streaming of large data.
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
    return "Route not found, but handled."
```

---

## Tools & Request Utilities

Blazeio includes several useful tools to make handling requests easier:

### Request Tools

- **Request.stream_chunks**: Stream request data in chunks, ideal for large file uploads or slow connections.
    ```python
    async for chunk in Blazeio.Request.stream_chunks(r):
        # Process each chunk
    ```

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
    async for file_chunk in Blazeio.Request.get_upload(r):
        if file_chunk is not None:
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

loop = new_event_loop()

web = loop.run_until_complete(io.App.init())

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
        if r.method in ["GET", "OPTIONS", "HEAD"]:
            json_data = await io.Request.get_params(r)
        else:
            json_data = await io.Request.get_json(r)

        r.json_data = json_data

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
    loop.run_until_complete(Server.setup())

    HOST = "0.0.0.0"
    PORT = "8000"

    web.runner(HOST, PORT, backlog=5000)
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

---

## Contributing

If you would like to contribute to Blazeio, feel free to fork the repository and submit a pull request. Bug reports and feature requests are also welcome!

---

## License

Blazeio is open-source and licensed under the MIT License.

---
