#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject* url_to_host(PyObject* self, PyObject* args, PyObject* kwargs) {
    const char *url;
    PyObject *params;
    int parse_params = 0;

    static char *kwlist[] = {"url", "params", "parse_params", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sO|p", kwlist, &url, &params, &parse_params))
        return NULL;

    if (!PyDict_Check(params)) {
        PyErr_SetString(PyExc_TypeError, "params must be a dict");
        return NULL;
    }

    const char *scheme_sep = "://";
    const char *host_sep = "/";
    const char *param_sep = "?";
    const char *port_sep = ":";

    PyObject *hostname = NULL, *path = NULL, *query = NULL;
    int port = 0;

    // Convert escaped slashes
    char *url_copy = strdup(url);
    for (char *p = url_copy; *p; ++p)
        if (p[0] == '\\' && p[1] == '/') { memmove(p, p + 1, strlen(p)); }

    char *host_start = strstr(url_copy, scheme_sep);
    if (!host_start) {
        free(url_copy);
        Py_RETURN_NONE;
    }
    host_start += strlen(scheme_sep);

    char *host = strdup(host_start);
    char *slash = strchr(host, '/');
    char *qmark = strchr(host, '?');

    if (!slash && qmark) {
        size_t len = qmark - host;
        char *temp = malloc(len + 2 + strlen(qmark) + 1);
        memcpy(temp, host, len);
        temp[len] = '/';
        strcpy(temp + len + 1, qmark);
        free(host);
        host = temp;
    } else if (!slash) {
        host = realloc(host, strlen(host) + 2);
        strcat(host, "/");
    }

    char *path_part = strchr(host, '/');
    if (path_part) {
        *path_part = '\0';
        ++path_part;
    }

    char *port_part = strchr(host, ':');
    if (port_part) {
        *port_part = '\0';
        ++port_part;
        port = atoi(port_part);
    }

    char *query_part = NULL;
    if (path_part) {
        query_part = strchr(path_part, '?');
        if (query_part) {
            *query_part = '\0';
            ++query_part;
        }
    }

    if (!port) {
        if (strncmp(url_copy, "https", 5) == 0)
            port = 443;
        else
            port = 80;
    }

    PyObject *py_host = PyUnicode_FromString(host);
    PyObject *py_path = path_part ? PyUnicode_FromFormat("/%s", path_part) : PyUnicode_FromString("/");
    
    if (query_part) {
        if (strchr(query_part, '=')) {
            PyObject *query_str = PyUnicode_FromFormat("?%s", query_part);
            PyUnicode_Append(&py_path, query_str);
            Py_DECREF(query_str);
        }
    }

    if (PyDict_Size(params) > 0) {
        PyObject *items = PyDict_Items(params);
        Py_ssize_t len = PyList_Size(items);
        PyObject *query = PyUnicode_FromString("?");

        for (Py_ssize_t i = 0; i < len; ++i) {
            PyObject *item = PyList_GetItem(items, i);
            PyObject *key = PyTuple_GetItem(item, 0);
            PyObject *value = PyTuple_GetItem(item, 1);
            PyObject *encoded = PyUnicode_FromFormat("%s%s=%S", (i == 0) ? "" : "&", PyUnicode_AsUTF8(key), value);
            PyUnicode_Append(&query, encoded);
            Py_DECREF(encoded);
        }
        Py_DECREF(items);
        PyUnicode_Append(&py_path, query);
        Py_DECREF(query);
    }

    PyObject *result = PyTuple_Pack(3, py_host, PyLong_FromLong(port), py_path);
    Py_DECREF(py_host);
    Py_DECREF(py_path);
    free(url_copy);
    free(host);
    return result;
}

static PyMethodDef Methods[] = {
    {"url_to_host", (PyCFunction)url_to_host, METH_VARARGS | METH_KEYWORDS, "Parse URL into host, port, and path."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef Blazeio_iourllibmodule = {
    PyModuleDef_HEAD_INIT,
    "Blazeio_iourllib",
    NULL,
    -1,
    Methods
};

PyMODINIT_FUNC PyInit_Blazeio_iourllib(void) {
    return PyModule_Create(&Blazeio_iourllibmodule);
}