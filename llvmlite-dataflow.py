"""
    Build dataflow and controlflow graphs from LLVM Bitcode

    Based on: github.com/pfalcon/graph-llvm-ir
        but with a port from the old Python  github.com/llvmpy/llvmpy
        to the better maintained github.com/numba/llvmlite
"""
import argparse
import re

import llvmlite.binding as llvm 
from llvmlite.ir import Block, Module, Constant

#USE_CLUSTERS = 0
CLUSTER_EDGES = 0
INV_NODES = 0
#EXPLICIT_CONTROL = 0
#CONTROL_BETWEEN_DATAFLOW_TREES = 1


def number_tmps(mod: Module):
    """
        This function establishes explicit names for nameless numeric
        temporaries in IR. It also should give human-readable IDs to each
        statement in IR. Actually, as this is SSA, it uses result temporary
        name as an ID for statement. And fails here, because void-typed
        statements do not allow to set temporary name. So, this needs rework,
        and so far worked around during graph construction.
    """
    tmp_i = 1
    for func in mod.functions:
        # print(func)
        for block in func.blocks:
            # print(f"basic block name: {block}")
            for inst in block.instructions:
                if str(inst.type) != "void" and not inst.name:
                    inst.name = f"t{tmp_i}"
                    tmp_i += 1


DEMANGLER = r"_Z(\d+)([a-z_A-Z][a-z_A-Z_0-9]*)"
def demangle_fname(name: str) -> str:
    """ Get the demangled name of a function """
    m = re.search(DEMANGLER, name)
    if m:
        return m.group(2)[0:int(m.group(1))]
    else:
        return name


class Graph:
    """
        Graph datastructure that houses the CFGs and DFGs
    """
    def __init__(self, _f, _out, _options):
        self.f = _f
        self.out = _out
        self.options = _options
        self.edges = []
        self.anon_bblock_cnt = 0
        self.anon_bblock_names = {}
        self.void_instr_cnt = 0
        self.void_instr_names = {}

    def write(self, line=""):
        """
            Write to output file handler
        """
        self.out.write(line + "\n")

    def start_graph(self):
        """ Graph initialization """
        self.write("digraph G {")
        self.write("compound=true")
        if self.options.dag_control:
            self.write("rankdir=BT")
        if self.options.block_edges and not self.options.block_edges_helpers:
            # If we use cluster edges w/o intervening nodes, we need to bump
            # rank (vertical) separation, because otherwise there's very
            # little vert. space left to render edges after cutting out
            # cluster rectangle
            self.write("ranksep=1")
        self.write(f'label="Graph for function: {demangle_fname(self.f.name)}\nBlack edges - dataflow, red edges - control flow"')

    def edge(self, edge_fro, edge_to, extra=""):
        """ Add an edge """
        self.edges.append(f"\"{edge_fro}\" -> \"{edge_to}\"{extra}")

    def block_name(self, block):
        """ 
            Returns basic block name, i.e. its entry label, or made name
            if label if absent. 
        """
        if block.name:
            return block.name
        if block in self.anon_bblock_names:
            return self.anon_bblock_names[block]
        self.anon_bblock_cnt += 1
        name = f"unk_block_{self.anon_bblock_cnt}"
        self.anon_bblock_names[block] = name
        return name

    def instr_name(self, i):
        """
            Returns instruction name, for which result variable name is used.
            If result variable name is absent (void statement), make up name.
        """
        if i in self.void_instr_names:
            return self.void_instr_names[i]
        name = i.name
        if not name:
            self.void_instr_cnt += 1
            name = f"_{self.void_instr_cnt}"
            self.void_instr_names[i] = name
        return name

    def declare_clusters(self):
        """ Declare clusters """
        if self.options.block:
            # Pre-allocate label nodes to subgraphs, otherwise Graphviz puts them to wrong subgraphs
            for block in self.f.basic_blocks:
                name = self.block_name(block)
#                    if not self.options.block_edges_helpers:
                self.write(f"subgraph \"cluster_{name}\" {{")

                if not self.options.block_edges:
                    self.write(f'\"{name}\" [label="label: \"{name}\""]')
                elif self.options.block_edges_helpers:
                    self.write(f'\"{name}\" [shape=point height=0.02 width=0.02 color=red fixedsize=true]')

#                    if not self.options.block_edges_helpers:
                self.write("}")
            self.write()


    def render(self):
        """ Render the graph """
#        print `f`
        self.start_graph()
        self.declare_clusters()
        # lab = 1
        for block in self.f.blocks:
            block_name = self.block_name(block)
            self.edges = []
            if self.options.block:
                self.write(f"subgraph \"cluster_{block_name}\" {{")
                self.write(f"label={block_name}")
#            if not self.options.block_edges:
#                self.write('\"%s\" [label="label: %s"]' % (block_name, block_name))
#           elif self.options.block_edges_helpers:
#               self.write('\"%s\" [shape=point]' % (block.name))

            # Create block entry label node and edge from it to first IR instruction
            if not self.options.block_edges or self.options.block_edges_helpers:
                attr = "[color=red]"
                if block.name == "entry":
                    attr += "[weight=5]"
                if self.options.block_edges:
                    attr += f"[lhead=\"cluster_{block_name}\"]"
                if self.options.control:
                    if list(block.instructions)[0].name == "":
                        instr_name = self.instr_name(list(block.instructions)[0])
                        self.edge(block_name, instr_name, attr)
                    else:
                        self.edge(block_name, list(block.instructions)[0].name, attr)

            if self.options.dag_control:
                last_void_inst = block_name
                for i in block.instructions:
                    if str(i.type) == "void":
                        instr_name = self.instr_name(i)
#                        self.edge(last_void_inst, instr_name, "[color=blue]")
                        self.edge(instr_name, last_void_inst, "[color=blue dir=back]")
                        last_void_inst = instr_name

            last_inst_name = None
            for i in block.instructions:
                instr_name = self.instr_name(i)
                cleaned_label = "_".join(str(i).split("\""))
                self.write(f'\"{instr_name}\" [label="{cleaned_label}"]')
                if self.options.control:
                    if last_inst_name:
                        self.edge(last_inst_name, instr_name, "[color=red weight=2]")
                else:
                    if i.opcode == "br" and len(i.operands) == 1:
                        self.edge(last_inst_name, instr_name, "[color=red]")

                for a in i.operands:
                    if isinstance(a, Constant) and not a.name:
                        arg_val = a
                    else:
                        arg_val = a.name
                    if i.opcode == "br" and isinstance(a, Block):
                        # For jump targets, we jump from current node to label (arg)
                        if self.options.block_edges and not self.options.block_edges_helpers:
                            arg_val = a.instructions[0].name
                        attrs = "[color=red]"
                        if self.options.block_edges:
                            attrs += f"[color=red][lhead=\"cluster_{a.name}\"]\
                                [ltail=\"cluster_{block_name}\"][weight=5]"
                            if self.options.block_edges_helpers:
                                attrs += "[arrowhead=none]"
                        self.edge(instr_name, arg_val, attrs)
                    else:
                        # For data, flow is from opearnd to operation
                        self.edge(arg_val, instr_name)
                last_inst_name = instr_name
            if self.options.block:
                self.write("}")
            for edge in self.edges:
                self.write(edge)
            self.write()
        self.write("}")


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        prog="llvm_dataflow",
        description='Generate dataflow and controlflow graphs from LLVM Bitcode'
        # usage="llvm_dataflow <file.ll>"
        )
    argparser.add_argument('file', help="path of *.ll LLVM bitcode file to analyze")
    argparser.add_argument('-b', '--block',
        action="store_true",
        default=False,
        help="draw basic blocks as clusters (default)")
    argparser.add_argument('-c', '--control',
        action="store_true",
        help="draw explicit control flow based on instruction order (default)")
    argparser.add_argument('-d', '--dag-control',
        action="store_true",
        help="analyze DAGs in a basic block and draw implied control flow among\
            them (consider using --no-control)")
    argparser.add_argument('-e', '--block-edges',
        action="store_true", default=False,
        help="(try to) draw inter-block edges between blocks, not between nodes")
    argparser.add_argument('-f', '--block-edges-helpers',
        action="store_true", default=False,
        help="Add Graphviz-specific hacks to produce better layout")

    args = argparser.parse_args()

    if not args.control and not args.dag_control:
        args.control = True


    # llvm.initialize()
    with open(args.file, 'r', encoding="utf-8") as asm:
        asm_file = asm.read()
        # print(asm_file)
        module = llvm.parse_assembly(asm_file)

    number_tmps(module)

    for f in module.functions:
        if not f.is_declaration:
            print(f"Writing .{f.name}.dot")
            with open(f".{f.name}.dot", 'w', encoding="utf-8") as out:
                g = Graph(f, out, args)
                g.render()
