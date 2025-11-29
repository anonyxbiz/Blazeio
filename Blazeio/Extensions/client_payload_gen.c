#include <Python.h>
#include <string.h>
#include <stdlib.h>

#define STACK_ALLOC_THRESHOLD 2048

typedef struct {
    const char *str;
    Py_ssize_t len;
} StringWithLength;

typedef struct {
    StringWithLength key;
    StringWithLength value;
} HeaderEntry;

static Py_ssize_t calculate_total_size_and_extract(
    const char *method, const char *path, const char *http_version, 
    PyObject *headers, HeaderEntry **header_entries_out) 
{
    if (!method || !path || !http_version || !headers) {
        return 0;
    }

    Py_ssize_t method_len = strlen(method);
    Py_ssize_t path_len = strlen(path);
    Py_ssize_t http_version_len = strlen(http_version);

    Py_ssize_t size = method_len + path_len + http_version_len + 12; // "  HTTP/\r\n"

    Py_ssize_t dict_size = PyDict_Size(headers);
    HeaderEntry *header_entries = PyMem_New(HeaderEntry, dict_size);
    if (!header_entries) {
        PyErr_NoMemory();
        return 0;
    }

    PyObject *key, *value;
    Py_ssize_t pos = 0;
    Py_ssize_t i = 0;

    while (PyDict_Next(headers, &pos, &key, &value)) {
        const char *key_str = PyUnicode_AsUTF8AndSize(key, &header_entries[i].key.len);
        const char *value_str = PyUnicode_AsUTF8AndSize(value, &header_entries[i].value.len);
        
        if (!key_str || !value_str) {
            PyMem_Free(header_entries);
            PyErr_SetString(PyExc_TypeError, "Header keys and values must be strings");
            return 0;
        }
        
        header_entries[i].key.str = key_str;
        header_entries[i].value.str = value_str;
        
        size += header_entries[i].key.len + header_entries[i].value.len + 4; // ": \r\n"
        i++;
    }

    size += 2; // Final CRLF
    *header_entries_out = header_entries;
    return size;
}

static PyObject* gen_payload(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char *kwlist[] = {"method", "headers", "path", "host", "port", "http_version", NULL};

    char *method = NULL;
    PyObject *headers = NULL;
    char *path = "/";
    char *host = NULL;
    int port = 0;
    char *http_version = "1.1";

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sO|ssis", kwlist, &method, &headers, &path, &host, &port, &http_version)) {
        return NULL;
    }

    if (!method || !*method) {
        PyErr_SetString(PyExc_ValueError, "Method cannot be empty");
        return NULL;
    }
    
    if (!headers || !PyDict_Check(headers)) {
        PyErr_SetString(PyExc_TypeError, "headers must be a dictionary");
        return NULL;
    }

    HeaderEntry *header_entries = NULL;
    size_t buf_size = calculate_total_size_and_extract(method, path, http_version, headers, &header_entries);
    if (buf_size == 0) {
        return NULL;
    }

    char stack_buffer[STACK_ALLOC_THRESHOLD];
    char *buffer = (buf_size <= STACK_ALLOC_THRESHOLD) ? stack_buffer : malloc(buf_size);
    if (!buffer && buf_size > STACK_ALLOC_THRESHOLD) {
        PyMem_Free(header_entries);
        PyErr_NoMemory();
        return NULL;
    }
    
    char *pos = buffer;

    if (strcmp(method, "CONNECT") == 0) {
        if (port <= 0 || !host) {
            if (buf_size > STACK_ALLOC_THRESHOLD) free(buffer);
            PyMem_Free(header_entries);
            PyErr_SetString(PyExc_ValueError, "CONNECT requires host and port");
            return NULL;
        }
        
        size_t host_len = strlen(host);
        memcpy(pos, method, strlen(method));
        pos += strlen(method);
        *pos++ = ' ';
        memcpy(pos, host, host_len);
        pos += host_len;
        *pos++ = ':';
        int port_len = snprintf(pos, 12, "%d", port);
        pos += port_len - 1;
        memcpy(pos, " HTTP/", 6);
        pos += 6;
        memcpy(pos, http_version, strlen(http_version));
        pos += strlen(http_version);
        memcpy(pos, "\r\n", 2);
        pos += 2;
    } else {
        memcpy(pos, method, strlen(method));
        pos += strlen(method);
        *pos++ = ' ';
        memcpy(pos, path, strlen(path));
        pos += strlen(path);
        memcpy(pos, " HTTP/", 6);
        pos += 6;
        memcpy(pos, http_version, strlen(http_version));
        pos += strlen(http_version);
        memcpy(pos, "\r\n", 2);
        pos += 2;
    }

    // Add headers
    Py_ssize_t num_headers = PyDict_Size(headers);
    for (Py_ssize_t i = 0; i < num_headers; i++) {
        memcpy(pos, header_entries[i].key.str, header_entries[i].key.len);
        pos += header_entries[i].key.len;
        memcpy(pos, ": ", 2);
        pos += 2;
        memcpy(pos, header_entries[i].value.str, header_entries[i].value.len);
        pos += header_entries[i].value.len;
        memcpy(pos, "\r\n", 2);
        pos += 2;
    }

    // Add final CRLF
    memcpy(pos, "\r\n", 2);
    pos += 2;

    PyObject *result = PyBytes_FromStringAndSize(buffer, pos - buffer);
    PyMem_Free(header_entries);
    if (buf_size > STACK_ALLOC_THRESHOLD) free(buffer);
    return result;
}

static PyMethodDef module_methods[] = {
    {"gen_payload", (PyCFunction)gen_payload, METH_VARARGS | METH_KEYWORDS, 
     "Generate HTTP payload bytes from method, headers, path, and HTTP version"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef client_payload_genmodule = {
    PyModuleDef_HEAD_INIT,
    "client_payload_gen",
    NULL,
    -1,
    module_methods
};

PyMODINIT_FUNC PyInit_client_payload_gen(void) {
    return PyModule_Create(&client_payload_genmodule);
}