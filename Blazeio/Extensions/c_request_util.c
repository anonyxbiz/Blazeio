#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

/*
 * All buffers are heap-allocated and sized from the actual input length, so
 * there is no fixed-size stack buffer to overflow.
 *
 *  - decode: output is never longer than input (each %XX shrinks 3 -> 1)
 *  - encode: output is at most 3x input
 */

/* ---------- character helpers (all take unsigned char: no UB on bytes >= 0x80) ---------- */

static int is_hex_char(unsigned char c) {
    return (c >= '0' && c <= '9') ||
           (c >= 'A' && c <= 'F') ||
           (c >= 'a' && c <= 'f');
}

static int hex_char_to_int(unsigned char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return c - 'a' + 10;
}

static int should_encode(unsigned char c) {
    /* Leave alphanumerics and -_.~ alone (RFC 3986 unreserved set).
       Explicit ASCII checks so behavior doesn't depend on the C locale. */
    return !((c >= '0' && c <= '9') ||
             (c >= 'A' && c <= 'Z') ||
             (c >= 'a' && c <= 'z') ||
             c == '-' || c == '_' || c == '.' || c == '~');
}

static void encode_char(unsigned char c, char* output) {
    static const char hex_chars[] = "0123456789ABCDEF";
    output[0] = '%';
    output[1] = hex_chars[c >> 4];
    output[2] = hex_chars[c & 0xF];
}

/* ---------- core implementations (bounded, no NUL-termination assumptions) ---------- */

static PyObject* decode_bytes(const char* input, Py_ssize_t input_len) {
    if (input_len == 0) {
        return PyUnicode_FromStringAndSize("", 0);
    }

    char* output = (char*)PyMem_Malloc((size_t)input_len);
    if (!output) return PyErr_NoMemory();

    char* out_ptr = output;
    const unsigned char* in_ptr = (const unsigned char*)input;
    const unsigned char* end = in_ptr + input_len;

    while (in_ptr < end) {
        /* need '%' plus two more bytes: end - in_ptr >= 3 */
        if (*in_ptr == '%' && (end - in_ptr) >= 3 &&
            is_hex_char(in_ptr[1]) && is_hex_char(in_ptr[2])) {
            *out_ptr++ = (char)((hex_char_to_int(in_ptr[1]) << 4) |
                                 hex_char_to_int(in_ptr[2]));
            in_ptr += 3;
        } else {
            *out_ptr++ = (char)*in_ptr++;
        }
    }

    /* "replace": a decoded %XX sequence may not be valid UTF-8; don't raise. */
    PyObject* result = PyUnicode_DecodeUTF8(output, out_ptr - output, "replace");
    PyMem_Free(output);
    return result;
}

static PyObject* encode_bytes(const char* input, Py_ssize_t input_len) {
    if (input_len == 0) {
        return PyUnicode_FromStringAndSize("", 0);
    }
    if (input_len > PY_SSIZE_T_MAX / 3) {
        return PyErr_NoMemory();
    }

    char* output = (char*)PyMem_Malloc((size_t)input_len * 3);
    if (!output) return PyErr_NoMemory();

    char* out_ptr = output;
    const unsigned char* in_ptr = (const unsigned char*)input;
    const unsigned char* end = in_ptr + input_len;

    while (in_ptr < end) {
        if (should_encode(*in_ptr)) {
            encode_char(*in_ptr, out_ptr);
            out_ptr += 3;
        } else {
            *out_ptr++ = (char)*in_ptr;
        }
        in_ptr++;
    }

    PyObject* result = PyUnicode_FromStringAndSize(output, out_ptr - output);
    PyMem_Free(output);
    return result;
}

/* Bounded substring search (like memmem, which isn't portable).
   Returns pointer to first match within [hay, hay+hay_len), or NULL. */
static const char* find_sub(const char* hay, Py_ssize_t hay_len,
                            const char* needle, Py_ssize_t needle_len) {
    if (needle_len <= 0 || hay_len < needle_len) return NULL;
    const char* last = hay + (hay_len - needle_len);
    for (const char* p = hay; p <= last; p++) {
        if (*p == *needle && memcmp(p, needle, (size_t)needle_len) == 0) {
            return p;
        }
    }
    return NULL;
}

/* ---------- Python-facing functions ---------- */

static PyObject* url_decode_sync(PyObject* self, PyObject* args) {
    const char* input;
    Py_ssize_t input_len;

    if (!PyArg_ParseTuple(args, "s#", &input, &input_len)) {
        return NULL;
    }
    return decode_bytes(input, input_len);
}

static PyObject* url_encode_sync(PyObject* self, PyObject* args) {
    const char* input;
    Py_ssize_t input_len;

    if (!PyArg_ParseTuple(args, "s#", &input, &input_len)) {
        return NULL;
    }
    return encode_bytes(input, input_len);
}

static PyObject* get_params_sync(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char* kwlist[] = {"r", "url", "q", "o", "y", NULL};
    PyObject* r = NULL;
    const char* url = NULL;
    const char* q = "?";
    const char* o = "&";
    const char* y = "=";

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|Ossss", kwlist,
                                     &r, &url, &q, &o, &y)) {
        return NULL;
    }

    Py_ssize_t q_len = (Py_ssize_t)strlen(q);
    Py_ssize_t o_len = (Py_ssize_t)strlen(o);
    Py_ssize_t y_len = (Py_ssize_t)strlen(y);
    if (q_len == 0 || o_len == 0 || y_len == 0) {
        PyErr_SetString(PyExc_ValueError, "q, o and y delimiters must be non-empty");
        return NULL;
    }

    /* `tail` (if used) must stay alive for as long as we read from its buffer. */
    PyObject* tail = NULL;
    const char* src = NULL;
    Py_ssize_t src_len = 0;

    if (r != NULL && r != Py_None) {
        tail = PyObject_GetAttrString(r, "tail");
        if (!tail) return NULL;

        src = PyUnicode_AsUTF8AndSize(tail, &src_len);
        if (!src) {
            Py_DECREF(tail);
            return NULL;
        }
    } else if (url != NULL) {
        src = url;
        src_len = (Py_ssize_t)strlen(url);
    } else {
        PyErr_SetString(PyExc_ValueError, "Either r or url must be provided");
        return NULL;
    }

    PyObject* dict = PyDict_New();
    if (!dict) {
        Py_XDECREF(tail);
        return NULL;
    }

    const char* q_pos = find_sub(src, src_len, q, q_len);
    if (!q_pos) {
        Py_XDECREF(tail);
        return dict;  /* no query string: empty dict */
    }

    const char* pos = q_pos + q_len;
    const char* end = src + src_len;

    while (pos < end) {
        /* Isolate one "key=value" pair: [pos, pair_end) */
        const char* amp = find_sub(pos, end - pos, o, o_len);
        const char* pair_end = amp ? amp : end;

        const char* eq = find_sub(pos, pair_end - pos, y, y_len);
        if (eq) {
            PyObject* key = decode_bytes(pos, eq - pos);
            PyObject* value = key ? decode_bytes(eq + y_len, pair_end - (eq + y_len)) : NULL;

            if (!key || !value) {
                Py_XDECREF(key);
                Py_XDECREF(value);
                Py_DECREF(dict);
                Py_XDECREF(tail);
                return NULL;
            }

            int rc = PyDict_SetItem(dict, key, value);
            Py_DECREF(key);
            Py_DECREF(value);
            if (rc < 0) {
                Py_DECREF(dict);
                Py_XDECREF(tail);
                return NULL;
            }
        }
        /* pairs without a '=' are skipped */

        pos = amp ? amp + o_len : end;
    }

    Py_XDECREF(tail);
    return dict;
}

static PyMethodDef RequestMethods[] = {
    {"url_decode_sync", url_decode_sync, METH_VARARGS, "Decode URL-encoded string"},
    {"url_encode_sync", url_encode_sync, METH_VARARGS, "Encode string for URL"},
    {"get_params_sync", (PyCFunction)(void(*)(void))get_params_sync,
     METH_VARARGS | METH_KEYWORDS, "Get URL parameters as dict"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef c_request_utilmodule = {
    PyModuleDef_HEAD_INIT,
    "c_request_util",
    "Optimized Request utilities in C",
    -1,
    RequestMethods
};

PyMODINIT_FUNC PyInit_c_request_util(void) {
    return PyModule_Create(&c_request_utilmodule);
}
