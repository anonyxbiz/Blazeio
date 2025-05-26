#include <Python.h>
#include <string.h>
#include <stdlib.h>

#define STACK_ALLOC_THRESHOLD 4096

typedef struct {
    const char *str;
    Py_ssize_t len;
} StringWithLength;

typedef struct {
    StringWithLength key;
    StringWithLength value;
} HeaderEntry;

static Py_ssize_t calculate_total_size_and_extract(
    PyObject *headers, HeaderEntry **header_entries_out, Py_ssize_t *total_entries_out) 
{
    if (!headers) {
        return 0;
    }

    Py_ssize_t dict_size = PyDict_Size(headers);
    if (dict_size == 0) {
        *header_entries_out = NULL;
        *total_entries_out = 0;
        return 2; // Just the final CRLF
    }

    // First pass: count total entries (including list expansions)
    Py_ssize_t total_entries = 0;
    PyObject *key, *value;
    Py_ssize_t pos = 0;
    
    while (PyDict_Next(headers, &pos, &key, &value)) {
        if (PyList_Check(value)) {
            total_entries += PyList_Size(value);
        } else {
            total_entries++;
        }
    }

    HeaderEntry *header_entries = PyMem_New(HeaderEntry, total_entries);
    if (!header_entries) {
        PyErr_NoMemory();
        return 0;
    }

    // Second pass: extract strings and calculate size
    pos = 0;
    Py_ssize_t total_entries_so_far = 0;
    Py_ssize_t size = 0;

    while (PyDict_Next(headers, &pos, &key, &value)) {
        const char *key_str = PyUnicode_AsUTF8AndSize(key, &header_entries[total_entries_so_far].key.len);
        if (!key_str) {
            PyMem_Free(header_entries);
            PyErr_SetString(PyExc_TypeError, "Header keys must be strings");
            return 0;
        }
        
        if (PyList_Check(value)) {
            Py_ssize_t list_size = PyList_Size(value);
            for (Py_ssize_t j = 0; j < list_size; j++) {
                PyObject *item = PyList_GetItem(value, j);
                const char *value_str = PyUnicode_AsUTF8AndSize(item, &header_entries[total_entries_so_far].value.len);
                
                if (!value_str) {
                    PyMem_Free(header_entries);
                    PyErr_SetString(PyExc_TypeError, "Header values must be strings");
                    return 0;
                }
                
                header_entries[total_entries_so_far].key.str = key_str;
                header_entries[total_entries_so_far].value.str = value_str;
                
                size += header_entries[total_entries_so_far].key.len + 
                        header_entries[total_entries_so_far].value.len + 4; // ": \r\n"
                total_entries_so_far++;
            }
        } else {
            const char *value_str = PyUnicode_AsUTF8AndSize(value, &header_entries[total_entries_so_far].value.len);
            
            if (!value_str) {
                PyMem_Free(header_entries);
                PyErr_SetString(PyExc_TypeError, "Header values must be strings");
                return 0;
            }
            
            header_entries[total_entries_so_far].key.str = key_str;
            header_entries[total_entries_so_far].value.str = value_str;
            
            size += header_entries[total_entries_so_far].key.len + 
                    header_entries[total_entries_so_far].value.len + 4; // ": \r\n"
            total_entries_so_far++;
        }
    }

    size += 2; // Final CRLF
    *header_entries_out = header_entries;
    *total_entries_out = total_entries;
    return size;
}

static PyObject* headers_to_http_bytes(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char *kwlist[] = {"headers", NULL};
    PyObject *headers = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &headers)) {
        return NULL;
    }
    
    if (!headers || !PyDict_Check(headers)) {
        PyErr_SetString(PyExc_TypeError, "headers must be a dictionary");
        return NULL;
    }

    HeaderEntry *header_entries = NULL;
    Py_ssize_t total_entries = 0;
    size_t buf_size = calculate_total_size_and_extract(headers, &header_entries, &total_entries);
    if (buf_size == 0 && PyErr_Occurred()) {
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

    // Add headers
    for (Py_ssize_t i = 0; i < total_entries; i++) {
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
    if (buf_size > STACK_ALLOC_THRESHOLD) {
        free(buffer);
    }
    
    return result;
}

static PyMethodDef module_methods[] = {
    {"headers_to_http_bytes", (PyCFunction)headers_to_http_bytes, METH_VARARGS | METH_KEYWORDS, 
     "Convert headers dictionary to HTTP bytes (headers + CRLF). Supports both single values and lists of values."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef server_tools_header_to_payload_module = {
    PyModuleDef_HEAD_INIT,
    "server_tools_header_to_payload",
    NULL,
    -1,
    module_methods
};

PyMODINIT_FUNC PyInit_server_tools_header_to_payload(void) {
    return PyModule_Create(&server_tools_header_to_payload_module);
}