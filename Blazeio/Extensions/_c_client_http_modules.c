#include <Python.h>
#include <string.h>
#include <stdlib.h>

typedef struct {
    PyObject_HEAD
    long x;
    long n;
} RangeGenerator;

typedef struct {
    PyObject_HEAD
} FastPayloadGenerator;

/* Helper function to calculate total size needed for payload */
static size_t calculate_total_size(const char *method, const char *path, 
                                 const char *http_version, PyObject *headers) {
    size_t size = strlen(method) + strlen(path) + strlen(http_version) + 12; // Base request line
    PyObject *key, *value;
    Py_ssize_t pos = 0;
    
    while (PyDict_Next(headers, &pos, &key, &value)) {
        const char *key_str = PyUnicode_AsUTF8(key);
        const char *value_str = PyUnicode_AsUTF8(value);
        size += strlen(key_str) + strlen(value_str) + 4; // ": \r\n"
    }
    size += 2; // Final CRLF
    return size;
}

/* Optimized payload generator */
static PyObject* FastPayloadGenerator_gen_payload(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char *kwlist[] = {"method", "headers", "path", "host", "port", "http_version", NULL};

    char *method = NULL;
    PyObject *headers = NULL;
    char *path = "/";
    char *host = NULL;
    int port = 0;
    char *http_version = "1.1";
    
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sO|ssis", kwlist, 
                                    &method, &headers, &path, &host, &port, &http_version)) {
        return NULL;
    }

    if (strlen(method) == 0) {
        PyErr_SetString(PyExc_ValueError, "Method cannot be empty");
        return NULL;
    }
    
    if (!PyDict_Check(headers)) {
        PyErr_SetString(PyExc_TypeError, "headers must be a dictionary");
        return NULL;
    }

    // Calculate total size needed
    size_t buf_size = calculate_total_size(method, path, http_version, headers);
    char *buffer = malloc(buf_size);
    if (!buffer) {
        PyErr_NoMemory();
        return NULL;
    }

    char *pos = buffer;
    
    // Build request line
    if (strcmp(method, "CONNECT") == 0) {
        if (port <= 0 || !host) {
            free(buffer);
            PyErr_SetString(PyExc_ValueError, "CONNECT requires host and port");
            return NULL;
        }
        pos += sprintf(pos, "%s %s:%d HTTP/%s\r\n", method, host, port, http_version);
    } else {
        pos += sprintf(pos, "%s %s HTTP/%s\r\n", method, path, http_version);
    }

    // Add headers
    PyObject *key, *value;
    Py_ssize_t dict_pos = 0;
    while (PyDict_Next(headers, &dict_pos, &key, &value)) {
        const char *key_str = PyUnicode_AsUTF8(key);
        const char *value_str = PyUnicode_AsUTF8(value);
        pos += sprintf(pos, "%s: %s\r\n", key_str, value_str);
    }

    // Add final CRLF
    strcpy(pos, "\r\n");
    pos += 2;

    PyObject *result = PyBytes_FromStringAndSize(buffer, pos - buffer);
    free(buffer);
    return result;
}

/* Range generator implementation (unchanged from your version) */
static PyObject* RangeGenerator_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    RangeGenerator *self = (RangeGenerator *)type->tp_alloc(type, 0);
    if (self) {
        self->x = 0;
        self->n = 0;
    }
    return (PyObject *)self;
}

static int RangeGenerator_init(RangeGenerator *self, PyObject *args, PyObject *kwds) {
    static char *kwlist[] = {"n", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "l", kwlist, &self->n)) {
        return -1;
    }
    if (self->n < 0) {
        PyErr_SetString(PyExc_ValueError, "n must be non-negative");
        return -1;
    }
    return 0;
}

static PyObject* RangeGenerator_next(RangeGenerator *self) {
    if (self->x >= self->n) {
        PyErr_SetNone(PyExc_StopIteration);
        return NULL;
    }
    return PyLong_FromLong(self->x++);
}

/* Type definitions and module initialization (unchanged) */
static void RangeGenerator_dealloc(RangeGenerator *self) {
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyTypeObject RangeGeneratorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "BlazeioClientHTTPModules.noallocrange",
    .tp_doc = "Efficient range generator without allocations",
    .tp_basicsize = sizeof(RangeGenerator),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = RangeGenerator_new,
    .tp_init = (initproc)RangeGenerator_init,
    .tp_dealloc = (destructor)RangeGenerator_dealloc,
    .tp_iter = PyObject_SelfIter,
    .tp_iternext = (iternextfunc)RangeGenerator_next,
};

static void FastPayloadGenerator_dealloc(FastPayloadGenerator *self) {
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject* FastPayloadGenerator_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
    FastPayloadGenerator *self = (FastPayloadGenerator *)type->tp_alloc(type, 0);
    return (PyObject *)self;
}

static int FastPayloadGenerator_init(FastPayloadGenerator *self, PyObject *args, PyObject *kwds) {
    return 0;
}

static PyMethodDef FastPayloadGenerator_methods[] = {
    {"gen_payload", (PyCFunction)FastPayloadGenerator_gen_payload, METH_VARARGS | METH_KEYWORDS, 
     "Generate HTTP payload from method, headers, path, and HTTP version"},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject FastPayloadGeneratorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "BlazeioClientHTTPModules.FastPayloadGenerator",
    .tp_doc = "Fast HTTP payload generator implemented in C",
    .tp_basicsize = sizeof(FastPayloadGenerator),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = FastPayloadGenerator_new,
    .tp_init = (initproc)FastPayloadGenerator_init,
    .tp_dealloc = (destructor)FastPayloadGenerator_dealloc,
    .tp_methods = FastPayloadGenerator_methods,
};

static PyModuleDef fastpayloadmodule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "BlazeioClientHTTPModules",
    .m_doc = "Fast HTTP payload generation module",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit_BlazeioClientHTTPModules(void) {
    PyObject *m;
    
    if (PyType_Ready(&RangeGeneratorType) < 0 || PyType_Ready(&FastPayloadGeneratorType) < 0) {
        return NULL;
    }
    
    m = PyModule_Create(&fastpayloadmodule);
    if (!m) return NULL;
    
    Py_INCREF(&RangeGeneratorType);
    if (PyModule_AddObject(m, "noallocrange", (PyObject *)&RangeGeneratorType) < 0) {
        Py_DECREF(&RangeGeneratorType);
        Py_DECREF(m);
        return NULL;
    }
    
    Py_INCREF(&FastPayloadGeneratorType);
    if (PyModule_AddObject(m, "FastPayloadGenerator", (PyObject *)&FastPayloadGeneratorType) < 0) {
        Py_DECREF(&FastPayloadGeneratorType);
        Py_DECREF(m);
        return NULL;
    }
    
    return m;
}