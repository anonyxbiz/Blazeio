#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

#define MAX_URL_LEN 4096
#define STACK_ALLOC_THRESHOLD 2048

// Simplified URL decode mapping - we'll handle the conversion manually
static int is_hex_char(char c) {
    return (c >= '0' && c <= '9') || (toupper(c) >= 'A' && toupper(c) <= 'F');
}

static int hex_char_to_int(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    return toupper(c) - 'A' + 10;
}

static PyObject* url_decode_sync(PyObject* self, PyObject* args) {
    const char* input;
    Py_ssize_t input_len;
    
    if (!PyArg_ParseTuple(args, "s#", &input, &input_len)) {
        return NULL;
    }

    char output[MAX_URL_LEN];
    char* out_ptr = output;
    const char* in_ptr = input;
    const char* end = input + input_len;

    while (in_ptr < end) {
        if (*in_ptr == '%' && in_ptr + 2 < end && 
            is_hex_char(in_ptr[1]) && is_hex_char(in_ptr[2])) {
            // Decode percent-encoded sequence
            char decoded = (hex_char_to_int(in_ptr[1]) << 4) | hex_char_to_int(in_ptr[2]);
            *out_ptr++ = decoded;
            in_ptr += 3;
        } else {
            *out_ptr++ = *in_ptr++;
        }
    }

    return PyUnicode_FromStringAndSize(output, out_ptr - output);
}

static int should_encode(char c) {
    // Encode all non-alphanumeric characters except -_.~
    return !(isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~');
}

static void encode_char(char c, char* output) {
    const char hex_chars[] = "0123456789ABCDEF";
    output[0] = '%';
    output[1] = hex_chars[(c >> 4) & 0xF];
    output[2] = hex_chars[c & 0xF];
}

static PyObject* url_encode_sync(PyObject* self, PyObject* args) {
    const char* input;
    Py_ssize_t input_len;
    
    if (!PyArg_ParseTuple(args, "s#", &input, &input_len)) {
        return NULL;
    }

    char output[MAX_URL_LEN * 3]; // Worst case: every character gets encoded
    char* out_ptr = output;
    const char* in_ptr = input;
    const char* end = input + input_len;

    while (in_ptr < end) {
        if (should_encode(*in_ptr)) {
            encode_char(*in_ptr, out_ptr);
            out_ptr += 3;
        } else {
            *out_ptr++ = *in_ptr;
        }
        in_ptr++;
    }

    return PyUnicode_FromStringAndSize(output, out_ptr - output);
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

    const char* params = NULL;
    Py_ssize_t params_len = 0;
    
    // Extract parameters from either r or url
    if (r != NULL && r != Py_None) {
        PyObject* tail = PyObject_GetAttrString(r, "tail");
        if (!tail) return NULL;
        
        Py_ssize_t tail_len;
        const char* tail_str = PyUnicode_AsUTF8AndSize(tail, &tail_len);
        if (!tail_str) {
            Py_DECREF(tail);
            return NULL;
        }
        
        const char* q_pos = strstr(tail_str, q);
        if (!q_pos) {
            Py_DECREF(tail);
            return PyDict_New();
        }
        
        params = q_pos + strlen(q);
        params_len = tail_len - (params - tail_str);
        Py_DECREF(tail);
    } else if (url != NULL) {
        const char* q_pos = strstr(url, q);
        if (!q_pos) {
            return PyDict_New();
        }
        params = q_pos + strlen(q);
        params_len = strlen(params);
    } else {
        PyErr_SetString(PyExc_ValueError, "Either r or url must be provided");
        return NULL;
    }

    PyObject* dict = PyDict_New();
    if (!dict) return NULL;

    const char* param_start = params;
    const char* param_end = params + params_len;
    
    while (param_start < param_end) {
        // Find key-value pair
        const char* eq_pos = strstr(param_start, y);
        if (!eq_pos || eq_pos >= param_end) break;
        
        const char* amp_pos = strstr(eq_pos + 1, o);
        if (!amp_pos) amp_pos = param_end;
        
        // Extract key and value
        PyObject* key = PyUnicode_DecodeUTF8(param_start, eq_pos - param_start, "replace");
        PyObject* value = PyUnicode_DecodeUTF8(eq_pos + 1, amp_pos - (eq_pos + 1), "replace");
        
        if (!key || !value) {
            Py_XDECREF(key);
            Py_XDECREF(value);
            Py_DECREF(dict);
            return NULL;
        }
        
        // URL decode and store in dict
        PyObject* decoded_key = url_decode_sync(self, PyTuple_Pack(1, key));
        PyObject* decoded_value = url_decode_sync(self, PyTuple_Pack(1, value));
        
        PyDict_SetItem(dict, decoded_key, decoded_value);
        
        Py_DECREF(key);
        Py_DECREF(value);
        Py_DECREF(decoded_key);
        Py_DECREF(decoded_value);
        
        param_start = amp_pos + 1;
    }

    return dict;
}

static PyMethodDef RequestMethods[] = {
    {"url_decode_sync", url_decode_sync, METH_VARARGS, "Decode URL-encoded string"},
    {"url_encode_sync", url_encode_sync, METH_VARARGS, "Encode string for URL"},
    {"get_params_sync", (PyCFunction)get_params_sync, METH_VARARGS | METH_KEYWORDS, 
     "Get URL parameters as dict"},
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