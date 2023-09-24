
## Generate LLVM dataflow graphs

This is a port of [graph-llvm-ir](github.com/pfalcon/graph-llvm-ir)
from the old [`llvmpy`](github.com/llvmpy/llvmpy) library to the new and better maintained [`numba.llvmlite`](github.com/numba/llvmlite).


### Prerequisites:

1. LLVM10 (llvmlite compatibility requirement)

2. Python3 with llvmlite (see https://github.com/numba/llvmlite)


### Usage:

Invoke the script as:

```bash
python3 llvm_dataflow.py <.ll file path>
```

This generates hidden `.dot` files for each function in the bitcode, 
e.g., `.<function_name>.dot`.



