# Blazeio.Dependencies.delimited_startswith
from ...Dependencies import *

def dstartswith(delimiter: any, data: any, sw: (tuple, list)):
    return data[:data[len(delimiter):].find(delimiter) + len(delimiter):] in sw

if __name__ == "__main__":
    ...