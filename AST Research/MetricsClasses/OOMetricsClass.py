import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import ast
from collections import defaultdict
import math
from multiprocessing.pool import ThreadPool
#ast_tree = None

#Step 1: Read python file and dump its AST tree
#file=open("./shor.py","r")
##print("Google Cirq Implementation:-----------------------------")
#file = open("./shors.py","r")
##print("Standard Implementation:-----------------------------")
#file=open("./test.py","r")
#print("Test Implementation:-----------------------------")
#tree=ast.parse(file.read())
##print(ast.dump(tree,indent=4))

class OOMetrics:
    def __init__(self,tree):
        self.tree=tree
        self.metrics={}
    def calculate_metrics(self):
        self.pool = ThreadPool()
        WMC_Thread = self.pool.apply_async(self.__WMC)
        NOC_DIT_Thread = self.pool.apply_async(self.__NOC_DIT)
        coupling_Thread = self.pool.apply_async(self.__CBO)
        WMC_Thread.wait()
        NOC_DIT_Thread.wait()
        coupling_Thread.wait()
        WMC = WMC_Thread.get()
        NOC,DIT=NOC_DIT_Thread.get()
        CBO = coupling_Thread.get()
        self.metrics = {
            "WMC" : WMC,
            "NOC" : NOC,
            "DIT" : DIT,
            "CBO" : CBO
        }
        return self.metrics
    def getMetrics(self):
        return self.metrics

    def __WMC(self):
        methods = MethodCollector()
        def calculate_wmc(class_methods):
            wmc = {class_name: len(methods) for class_name, methods in class_methods.items()}
            return wmc
        methods.visit(self.tree)
        wmc=calculate_wmc(methods.class_methods)
        return wmc
    def __NOC_DIT(self):
        inherit = InheritanceVisitor()
        inherit.visit(self.tree)
    
        def calculate_noc(inheritance):
            noc = {class_name: len(children) for class_name, children in inheritance.items()}
            return noc
    
        def calculate_dit(parent_of, class_name, depth_cache):
            """Calculate DIT by going UP the inheritance tree"""
            if class_name in depth_cache:
                return depth_cache[class_name]
        
            # If class has no parent in our code, it's at depth 1 (inherits from object)
            if class_name not in parent_of:
                depth_cache[class_name] = 1
                return 1
        
            # Otherwise, depth = parent's depth + 1
            parent = parent_of[class_name]
            parent_depth = calculate_dit(parent_of, parent, depth_cache)
            depth_cache[class_name] = parent_depth + 1
            return parent_depth + 1
    
        # Calculate NOC
        noc = calculate_noc(inherit.inheritance)
    
        # Calculate DIT (corrected)
        depth_cache = {}
        for class_name in inherit.classes:
            calculate_dit(inherit.parent_of, class_name, depth_cache)
    
        return noc, depth_cache
        # inherit=InheritanceVisitor()
        # inherit.visit(self.tree)
        # def calculate_noc(inheritance):
        #     noc = {class_name: len(children) for class_name, children in inheritance.items()}
        #     return noc
        # def calculate_dit(inheritance, class_name, depth_cache):
        #     if class_name in depth_cache:
        #         return depth_cache[class_name]

        #     if class_name not in inheritance:
        #         depth_cache[class_name] = 1
        #         return 1

        #     max_depth = 0
        #     for child in inheritance[class_name]:
        #         child_depth = calculate_dit(inheritance, child, depth_cache)
        #         max_depth = max(max_depth, child_depth)

        #     depth_cache[class_name] = max_depth + 1
        #     return max_depth + 1

        # depth_cache = {}
        # for class_name in inherit.classes:
        #     calculate_dit(inherit.inheritance, class_name, depth_cache)
        # return (calculate_noc(inherit.inheritance),depth_cache)

    def __CBO(self):
        def calculate_cbo(tree):
            """Calculate CBO - only count coupling to classes defined in the same module"""
            collector = CouplingCollector()
            collector.visit(tree)
    
            # Filter to only count references to classes actually defined in this code
            cbo = {}
            for class_name in collector.all_classes:
                # Count how many OTHER classes this class is coupled to
                coupled_classes = collector.class_references[class_name]
                # Filter to only classes defined in this module + common built-ins
                valid_couplings = {ref for ref in coupled_classes 
                                  if ref in collector.all_classes or ref in {'object', 'Exception', 'str', 'int', 'list', 'dict'}}
                cbo[class_name] = len(valid_couplings)
    
            return cbo
        return calculate_cbo(self.tree)
#OO metrics
#print("OO metrics----------")
#WMC
class MethodCollector(ast.NodeVisitor):
    def __init__(self):
        self.class_methods = defaultdict(list)
        self.current_class = None

    def visit_ClassDef(self, node):
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node):
        if self.current_class is not None:
            self.class_methods[self.current_class].append(node.name)
        self.generic_visit(node)

#NOC
class InheritanceVisitor(ast.NodeVisitor):
    def __init__(self):
        self.inheritance = defaultdict(list)  # parent -> [children]
        self.parent_of = {}  # child -> parent
        self.classes = set()
    
    def visit_ClassDef(self, node):
        class_name = node.name
        self.classes.add(class_name)
        
        for base in node.bases:
            if isinstance(base, ast.Name):
                parent_name = base.id
                self.inheritance[parent_name].append(class_name)
                self.parent_of[class_name] = parent_name
            elif isinstance(base, ast.Attribute):
                parent_name = base.value.id + "." + base.attr
                self.inheritance[parent_name].append(class_name)
                self.parent_of[class_name] = parent_name
        
        self.generic_visit(node)

#CBO
class CouplingCollector(ast.NodeVisitor):
    def __init__(self):
        self.class_references = defaultdict(set)  # class -> set of other classes it references
        self.current_class = None
        self.all_classes = set()  # Track all classes defined in the code
    
    def visit_ClassDef(self, node):
        self.current_class = node.name
        self.all_classes.add(node.name)
        
        # Handle inheritance (base classes)
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.class_references[self.current_class].add(base.id)
            elif isinstance(base, ast.Attribute):
                # Handle cases like module.ClassName
                base_name = self._get_full_name(base)
                if base_name:
                    self.class_references[self.current_class].add(base_name)
        
        self.generic_visit(node)
        self.current_class = None
    
    def visit_Call(self, node):
        if self.current_class:
            # Direct class instantiation: ClassName()
            if isinstance(node.func, ast.Name):
                class_name = node.func.id
                # Only count if it's likely a class (starts with uppercase)
                if class_name[0].isupper():
                    self.class_references[self.current_class].add(class_name)
            
            # Method calls on other objects: obj.method()
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    obj_name = node.func.value.id
                    # Skip 'self' references - we want coupling to OTHER classes
                    if obj_name != 'self':
                        # This is tricky - we'd need type inference to know the class
                        # For now, we can collect the object names
                        pass
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        if self.current_class and isinstance(node.value, ast.Name):
            obj_name = node.value.id
            # Skip 'self' references
            if obj_name != 'self':
                # Again, would need type inference to map to actual classes
                pass
        
        self.generic_visit(node)
    
    def visit_AnnAssign(self, node):
        """Handle type annotations like: param: ClassName"""
        if self.current_class and node.annotation:
            class_name = self._extract_type_name(node.annotation)
            if class_name:
                self.class_references[self.current_class].add(class_name)
        
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Handle function parameter annotations"""
        if self.current_class:
            # Check parameter annotations
            for arg in node.args.args:
                if arg.annotation:
                    class_name = self._extract_type_name(arg.annotation)
                    if class_name:
                        self.class_references[self.current_class].add(class_name)
            
            # Check return annotation
            if node.returns:
                class_name = self._extract_type_name(node.returns)
                if class_name:
                    self.class_references[self.current_class].add(class_name)
        
        self.generic_visit(node)
    
    def _extract_type_name(self, annotation):
        """Extract class name from type annotation"""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return self._get_full_name(annotation)
        return None
    
    def _get_full_name(self, node):
        """Get full dotted name from ast.Attribute"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_full_name(node.value)
            if base:
                return f"{base}.{node.attr}"
        return None

# def calculate_cbo(class_references):
#     cbo = {class_name: len(references) for class_name, references in class_references.items()}
#     return cbo

# visitor=CouplingCollector()
# visitor.visit(tree)
# cbo = calculate_cbo(visitor.class_references)
# for class_name, coupling in cbo.items():
#     #print(f"Class {class_name} has a CBO of {coupling}")

#RFC and RFC'
#file=open("./shor.py","r")
##print("Google Cirq Implementation:-----------------------------")
#file = open("./shors.py","r")
##print("Standard Implementation:-----------------------------")
#file=open("./test.py","r")
#print("Test Implementation:-----------------------------")
#tree=ast.parse(file.read())


# #Example usage
# file=open("Shape_Rectangle.py","r")
# tree=ast.parse(file.read())
# metrics_class_oo=OOMetrics(tree)
# metrics = metrics_class_oo.calculate_metrics()
# print("OO Metrics:", metrics)