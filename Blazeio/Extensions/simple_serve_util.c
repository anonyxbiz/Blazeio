#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>

typedef struct {
    PyObject_HEAD
    PyObject *headers;
    PyObject *cache_control;
    long CHUNK_SIZE;
    PyObject *r;
    long file_size;
    PyObject *filename;
    struct stat file_stats;
    time_t last_modified;
    PyObject *etag;
    PyObject *last_modified_str;
    int file_fd;
    PyObject *content_type;
    PyObject *content_disposition;
    long start;
    long end;
    PyObject *range_;
    int status;
} SimpleServeObject;

static int SimpleServe_init(SimpleServeObject *self, PyObject *args, PyObject *kwargs) {
    static char *kwlist[] = {"r", "file", "CHUNK_SIZE", "headers", "cache_control", "status", NULL};
    PyObject *r = NULL, *file = NULL, *headers = NULL, *cache_control = NULL;
    long CHUNK_SIZE = 1024;
    int status = 200;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|lOOi", kwlist, 
                                   &r, &file, &CHUNK_SIZE, &headers, &cache_control, &status))
        return -1;

    const char *file_path = PyUnicode_AsUTF8(file);
    if (!file_path) return -1;

    if (access(file_path, F_OK) != 0) {
        PyErr_SetString(PyExc_FileNotFoundError, "File not found");
        return -1;
    }

    self->r = r;
    Py_INCREF(r);
    
    self->CHUNK_SIZE = CHUNK_SIZE;
    self->status = status;
    
    self->file_fd = open(file_path, O_RDONLY);
    if (self->file_fd == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }

    if (fstat(self->file_fd, &self->file_stats) == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
        return -1;
    }
    
    self->file_size = self->file_stats.st_size;
    self->last_modified = self->file_stats.st_mtime;
    
    const char *basename = strrchr(file_path, '/');
    basename = basename ? basename + 1 : file_path;
    self->filename = PyUnicode_FromString(basename);
    if (!self->filename) return -1;
    
    self->etag = PyUnicode_FromFormat("BlazeIO--%s--%ld", basename, self->file_size);
    if (!self->etag) return -1;
    
    char last_modified[30];
    struct tm *tm = gmtime(&self->last_modified);
    strftime(last_modified, sizeof(last_modified), "%a, %d %b %Y %H:%M:%S GMT", tm);
    self->last_modified_str = PyUnicode_FromString(last_modified);
    if (!self->last_modified_str) return -1;
    
    self->headers = PyDict_New();
    if (!self->headers) return -1;
    PyDict_SetItemString(self->headers, "Accept-ranges", PyUnicode_FromString("bytes"));
    
    if (headers && PyDict_Check(headers)) {
        PyObject *key, *value;
        Py_ssize_t pos = 0;
        
        while (PyDict_Next(headers, &pos, &key, &value)) {
            PyDict_SetItem(self->headers, key, value);
        }
    }
    
    self->cache_control = cache_control ? cache_control : PyDict_New();
    Py_INCREF(self->cache_control);
    
    return 0;
}

static void SimpleServe_dealloc(SimpleServeObject *self) {
    if (self->file_fd != -1) close(self->file_fd);
    Py_XDECREF(self->headers);
    Py_XDECREF(self->cache_control);
    Py_XDECREF(self->r);
    Py_XDECREF(self->filename);
    Py_XDECREF(self->etag);
    Py_XDECREF(self->last_modified_str);
    Py_XDECREF(self->content_type);
    Py_XDECREF(self->content_disposition);
    Py_XDECREF(self->range_);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *SimpleServe_validate_cache(SimpleServeObject *self) {
    PyObject *headers = PyObject_GetAttrString(self->r, "headers");
    if (!headers) return NULL;
    
    PyObject *if_none_match = PyDict_GetItemString(headers, "If-none-match");
    if (if_none_match && PyUnicode_Compare(if_none_match, self->etag) == 0) {
        Py_DECREF(headers);
        PyErr_SetString(PyExc_Exception, "Not Modified");
        return PyLong_FromLong(304);
    }
    
    PyObject *if_modified_since = PyDict_GetItemString(headers, "If-modified-since");
    if (if_modified_since) {
        if (PyUnicode_Compare(if_modified_since, self->last_modified_str) >= 0) {
            Py_DECREF(headers);
            PyErr_SetString(PyExc_Exception, "Not Modified");
            return PyLong_FromLong(304);
        }
    }
    
    Py_DECREF(headers);
    Py_RETURN_NONE;
}

static PyObject *SimpleServe_prepare_metadata(SimpleServeObject *self) {
    PyObject *cache_result = SimpleServe_validate_cache(self);
    if (cache_result && PyLong_AsLong(cache_result) == 304) {
        return cache_result;
    }
    
    const char *ext = strrchr(PyUnicode_AsUTF8(self->filename), '.');
    if (ext) {
        if (strcmp(ext, ".html") == 0) {
            self->content_type = PyUnicode_FromString("text/html");
        } else if (strcmp(ext, ".css") == 0) {
            self->content_type = PyUnicode_FromString("text/css");
        } else if (strcmp(ext, ".js") == 0) {
            self->content_type = PyUnicode_FromString("application/javascript");
        } else if (strcmp(ext, ".json") == 0) {
            self->content_type = PyUnicode_FromString("application/json");
        }
    }
    
    if (!self->content_type) {
        self->content_type = PyUnicode_FromString("application/octet-stream");
    }
    
    self->content_disposition = PyUnicode_FromFormat("inline; filename=\"%s\"", 
                                                   PyUnicode_AsUTF8(self->filename));
    
    PyDict_SetItemString(self->headers, "Content-Type", self->content_type);
    PyDict_SetItemString(self->headers, "Content-Disposition", self->content_disposition);
    PyDict_SetItemString(self->headers, "Last-Modified", self->last_modified_str);
    PyDict_SetItemString(self->headers, "Etag", self->etag);
    
    PyObject *range_header = PyObject_GetAttrString(self->r, "headers");
    if (!range_header) return NULL;
    
    PyObject *range = PyDict_GetItemString(range_header, "Range");
    if (range) {
        const char *range_str = PyUnicode_AsUTF8(range);
        if (range_str) {
            long start, end;
            if (sscanf(range_str, "bytes=%ld-%ld", &start, &end) == 2) {
                self->start = start;
                self->end = end;
                self->status = 206;
                
                char content_range[100];
                snprintf(content_range, sizeof(content_range), 
                        "bytes %ld-%ld/%ld", start, end, self->file_size);
                PyDict_SetItemString(self->headers, "Content-Range", 
                                   PyUnicode_FromString(content_range));
            }
        }
    } else {
        self->start = 0;
        self->end = self->file_size;
        PyDict_SetItemString(self->headers, "Content-Length", 
                           PyLong_FromLong(self->file_size));
    }
    
    Py_DECREF(range_header);
    Py_RETURN_NONE;
}

static PyMethodDef SimpleServe_methods[] = {
    {"validate_cache", (PyCFunction)SimpleServe_validate_cache, METH_NOARGS, "Validate cache headers"},
    {"prepare_metadata", (PyCFunction)SimpleServe_prepare_metadata, METH_NOARGS, "Prepare response metadata"},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject SimpleServeType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "simple_serve_util.SimpleServe",
    .tp_doc = "High-performance file server",
    .tp_basicsize = sizeof(SimpleServeObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
    .tp_init = (initproc)SimpleServe_init,
    .tp_dealloc = (destructor)SimpleServe_dealloc,
    .tp_methods = SimpleServe_methods,
};

static PyModuleDef simple_serve_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "simple_serve_util",
    .m_doc = "Optimized file serving utilities",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit_simple_serve_util(void) {
    PyObject *m;
    
    if (PyType_Ready(&SimpleServeType) < 0)
        return NULL;

    m = PyModule_Create(&simple_serve_module);
    if (m == NULL)
        return NULL;

    Py_INCREF(&SimpleServeType);
    if (PyModule_AddObject(m, "SimpleServe", (PyObject *)&SimpleServeType) < 0) {
        Py_DECREF(&SimpleServeType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}