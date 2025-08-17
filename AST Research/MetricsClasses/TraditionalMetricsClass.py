import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import ast
from collections import defaultdict
import math
from multiprocessing.pool import ThreadPool
import builtins
import keyword
traditional_metrics_names=["LOC","Fan in","Fan out","CC","Length of Identifier"]

class TraditionalMetrics:
    def __init__(self,tree):
        self.tree=tree
        self.metrics={}
    def calculate_metrics(self):
        self.pool=ThreadPool()
        __loc_thread = self.pool.apply_async(self.__LOC)
        __fan_in_fan_out_thread = self.pool.apply_async(self.__fan_in_fan_out)
        __CC_thread = self.pool.apply_async(self.__CC)
        __length_of_identifier_thread = self.pool.apply_async(self.__length_of_identifier)
        __loc_thread.wait()
        __fan_in_fan_out_thread.wait()
        __CC_thread.wait()
        __length_of_identifier_thread.wait()
        __LOC = __loc_thread.get()
        __fan_in,__fan_out = __fan_in_fan_out_thread.get()
        __CC = __CC_thread.get()
        __length_of_identifier = __length_of_identifier_thread.get()
        self.metrics = {
            "LOC":__LOC,
            "Fan in":__fan_in,
            "Fan out":__fan_out,
            "CC":__CC,
            "Length of Identifier":__length_of_identifier
        }
        return self.metrics
        
    def __LOC(self):
        # Count actual lines of code, excluding blank lines and comments
        source_lines = ast.get_source_segment(compile(self.tree, '<string>', 'exec'), self.tree)
        if source_lines is None:
            # Fallback: count unique line numbers from AST nodes
            code_lines = set()
            for node in ast.walk(self.tree):
                if hasattr(node, 'lineno'):
                    code_lines.add(node.lineno)
            return len(code_lines)
        
        # Count non-empty, non-comment lines
        lines = source_lines.split('\n')
        loc = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                loc += 1
        return loc
        
    def __fan_in_fan_out(self):
        visitor = FunctionCallVisitor()
        visitor.visit(self.tree)
        def calculate_fan_in_out(callers, callees):
            fan_in = {func: len(callers[func]) for func in callers}
            fan_out = {func: len(callees[func]) for func in callees}
            return fan_in, fan_out
        return calculate_fan_in_out(visitor.callers, visitor.callees)
        
    def __CC(self):
        visitor = ComplexityVisitor()
        visitor.visit(self.tree)
        # Add 1 to each method's complexity (base complexity)
        cc_results = {}
        for method_name, complexity in visitor.methods.items():
            cc_results[method_name] = complexity + 1
        return cc_results
        
    def __length_of_identifier(self):
        visitor=IdentifierVisitor()
        visitor.visit(self.tree)
        try:
            print("Length of Identifier:", visitor.total_length, visitor.occurrences)
            res = visitor.total_length/visitor.occurrences
        except:
            res = -1
        return res
        
    def get_metrics(self):
        return self.metrics

class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.callers = defaultdict(set)   # key: callee, value: set of callers
        self.callees = defaultdict(set)   # key: caller, value: set of callees
        self.current_function = None
        self.current_class = None
        self.class_bases = {}

    def visit_ClassDef(self, node):
        self.class_bases[node.name] = [
            base.id for base in node.bases if isinstance(base, ast.Name)
        ]
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        func_name = self._qualify_function_name(node.name)
        prev_function = self.current_function
        self.current_function = func_name

        self.callers.setdefault(func_name, set())
        self.callees.setdefault(func_name, set())

        self.generic_visit(node)
        self.current_function = prev_function

    def visit_Call(self, node):
        if self.current_function:
            callee = self._get_callee_name(node.func)
            if callee and callee != "super":
                self.callees[self.current_function].add(callee)
                self.callers[callee].add(self.current_function)
        self.generic_visit(node)

    def _qualify_function_name(self, name):
        return f"{self.current_class}.{name}" if self.current_class else name
    def _get_callee_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "super":
                # Handle super().method()
                if self.current_class:
                    bases = self.class_bases.get(self.current_class, [])
                    if bases:
                        return f"{bases[0]}.{node.attr}"  # Assume single inheritance
            elif isinstance(node.value, ast.Name):
                if node.value.id == "self":
                    return f"{self.current_class}.{node.attr}" if self.current_class else node.attr
                else:
                    return f"{node.value.id}.{node.attr}"
            elif isinstance(node.value, ast.Attribute):
                return node.attr
        return None


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.methods = defaultdict(int)
        self.current_method = None
        self.current_class = ""
    
    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        if self.current_class:
            method_name = f"{self.current_class}.{node.name}"
        else:
            method_name = node.name
            
        old_method = self.current_method
        self.current_method = method_name
        
        # Initialize the method in the dictionary
        if method_name not in self.methods:
            self.methods[method_name] = 0
            
        self.generic_visit(node)
        self.current_method = old_method
    
    def visit_If(self, node):
        if self.current_method:
            self.methods[self.current_method] += 1 
        self.generic_visit(node)
        
    def visit_IfExp(self, node: ast.IfExp):
        if self.current_method:
            self.methods[self.current_method] += 1 
        self.generic_visit(node)
        
    def visit_For(self, node):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)
        
    def visit_While(self, node):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)
        
    def visit_AsyncFor(self, node: ast.AsyncFor):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)
        
    def visit_comprehension(self, node: ast.comprehension):
        if self.current_method:
            self.methods[self.current_method] += 1 + len(node.ifs)
        self.generic_visit(node)
        
    def visit_Assert(self, node):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_TryStar(self, node: ast.TryStar):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_match_case(self, node: ast.match_case):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_With(self, node):
        if self.current_method:
            self.methods[self.current_method] += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        if self.current_method:
            self.methods[self.current_method] += len(node.values) - 1
        self.generic_visit(node)

class IdentifierVisitor(ast.NodeVisitor):
    def __init__(self):
        self.total_length = 0
        self.occurrences = 0
        
    def increase_length(self, name):
        self.total_length += len(name)
        print(name)
        self.occurrences += 1
        
    def visit_ClassDef(self, node: ast.ClassDef):
        self.increase_length(node.name)
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.increase_length(node.name)
        # Count parameter names (these are ast.arg nodes, not ast.Name nodes)
        for arg in node.args.args:
            self.increase_length(arg.arg)
        self.generic_visit(node)
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.increase_length(node.name)
        # Count parameter names (these are ast.arg nodes, not ast.Name nodes)
        for arg in node.args.args:
            self.increase_length(arg.arg)
        self.generic_visit(node)
        
    def visit_Name(self, node: ast.Name):
        # Only count meaningful identifiers, skip common built-ins
        if node.id not in ['True', 'False', 'None']:
            self.increase_length(node.id)
        self.generic_visit(node)
        
    def visit_Attribute(self, node: ast.Attribute):
        # For attribute access like self.name, count the attribute name
        self.increase_length(node.attr)
        # Continue visiting the object being accessed (e.g., 'self' in 'self.name')
        self.generic_visit(node)

# class IdentifierVisitor(ast.NodeVisitor):
#     def __init__(self, exclude_builtins=True):
#         self.total_length = 0
#         self.occurrences = 0
#         self.exclude_builtins = exclude_builtins
        
#     def is_builtin_or_keyword(self, name):
#         """Check if a name is a built-in function/type or Python keyword."""
#         return (
#             hasattr(builtins, name) or  # Built-in functions, types, exceptions
#             keyword.iskeyword(name) or  # Python keywords like 'for', 'if', etc.
#             name in {'True', 'False', 'None'}  # Singleton constants
#         )
        
#     def increase_length(self, name):
#         if self.exclude_builtins and self.is_builtin_or_keyword(name):
#             return  # Skip built-in identifiers
            
#         self.total_length += len(name)
#         print(f"'{name}' (length: {len(name)})")
#         self.occurrences += 1
        
#     def visit_ClassDef(self, node: ast.ClassDef):
#         self.increase_length(node.name)
#         self.generic_visit(node)
        
#     def visit_FunctionDef(self, node: ast.FunctionDef):
#         self.increase_length(node.name)
#         # Count parameter names
#         for arg in node.args.args:
#             self.increase_length(arg.arg)
#         self.generic_visit(node)
        
#     def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
#         self.increase_length(node.name)
#         # Count parameter names
#         for arg in node.args.args:
#             self.increase_length(arg.arg)
#         self.generic_visit(node)
        
#     def visit_Name(self, node: ast.Name):
#         self.increase_length(node.id)
#         self.generic_visit(node)
        
#     def visit_Attribute(self, node: ast.Attribute):
#         # For attribute access like self.name, count the attribute name
#         self.increase_length(node.attr)
#         # Continue visiting the object being accessed (e.g., 'self' in 'self.name')
#         self.generic_visit(node)


# #Example usage
# file=open("Square.py","r")
# ##print("Google Cirq Implementation:-----------------------------")
# #file = open("./shors.py","r")
# ##print("Standard Implementation:-----------------------------")
# # file=open("./test.py","r")
# # #print("Test Implementation:-----------------------------")
# tree=ast.parse(file.read())
# metrics_class_trad=TraditionalMetrics(tree)
# metrics = metrics_class_trad.calculate_metrics()
# print("Traditional Metrics:", metrics)


