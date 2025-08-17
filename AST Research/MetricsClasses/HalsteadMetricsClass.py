import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import ast
from collections import defaultdict
import math
from multiprocessing.pool import ThreadPool
#ast_tree = None


halstead_metrics_names=["Program Vocabulary","Program Length","Estimated Program Length",
                  "Volume","Difficulty","Effort"]
class HalsteadMetrics:
    def __init__(self,tree):
        self.tree=tree
        self.pool=ThreadPool()
        self.metrics={}

    def calculate_metrics(self):
        self.operators = self.pool.apply_async(self.__collectOperators)
        self.operands = self.pool.apply_async(self.__collectOperands)
        #self.pool.join()
        self.operators.wait()
        self.operands.wait()
        n1,N1 = self.operators.get()
        #print("n1:",n1," N1:",N1)
        n2,N2=self.operands.get()
        #print("n1:",n2," N1:",N2)
        program_vocabulary = n1+n2
        program_length = N1+N2
        try:
            estimated_program_length = n1*math.log2(n1)+n2*math.log2(n2)
        except:
            estimated_program_length = -1
        try:
            volume=program_length*math.log2(program_vocabulary)
        except:
            volume=-1
        try:
            difficulty=(n1/2)*(N2/n2)
        except:
            difficulty=-1
        try:
            effort = difficulty*volume
        except:
            effort=-1
        self.metrics = {
            "Program Vocabulary" : program_vocabulary,
            "Program Length" : program_length,
            "Estimated Program Length" :  estimated_program_length,
            "Volume" : volume,
            "Difficulty" : difficulty,
            "Effort" : effort
        }
        return self.metrics
        #self.pool.join()

    def __collectOperators(self):
        operatorCollector = OperatorCollector() 
        operatorCollector.visit(self.tree)
        #print("Operators:",operatorCollector.operators)
        return (len(operatorCollector.operators),operatorCollector.total_operators)
    def __collectOperands(self):
        operandCollector=OperandCollector()
        operandCollector.visit(self.tree)
        return (len(operandCollector.operands),len(operandCollector.total_operands))
    def getMetrics(self):
        return self.metrics    



class OperatorCollector(ast.NodeVisitor):
    def __init__(self):
        self.operators=set()
        self.total_operators = 0

    def __increase_total(self):
        self.total_operators+=1
    
    def visit_For(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_While(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_If(self, node):
        self.operators.add(node.__class__.__name__)
        #print(node.__class__.__name__)
        if(node.orelse):
            #print(self.name(node))
            self.operators.add("Orelse")
            ##print("OrElse")
            self.__increase_total()
        self.__increase_total()
        #print(self.name(node))
        self.generic_visit(node)
    def visit_Return(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Pass(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Break(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Continue(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Subscript(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Slice(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)
    
    def visit_ListComp(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_SetComp(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_DictComp(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_GeneratorExp(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Call(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Attribute(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        ##print(node.__class__.__name__)
        self.__increase_total()
        self.generic_visit(node)

    def visit_Yield(self, node: ast):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total() 
        self.generic_visit(node)

    def visit_YieldFrom(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total() 
        self.generic_visit(node)

    def visit_Raise(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Assert(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_TypeAlias(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Try(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_TryStar(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_ExceptHandler(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_With(self,node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        self.operators.add(self.name(node.op))
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_BinOp(self, node):
        self.operators.add(self.name(node.op))
        #print(self.name(node.op))
        self.__increase_total()
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.operators.add(self.name(node.op))
        #print(self.name(node.op))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Compare(self, node):
        for op in node.ops:
            self.operators.add(self.name(op))
            ##print(name(op))
            #print(self.name(node))
            self.__increase_total()
        self.generic_visit(node)
        #print(self.name(node))
    def visit_Assign(self, node):
        self.operators.add(node.__class__.__name__)
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.operators.add(":")
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.operators.add(self.name(node.op)+"=")
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Delete(self, node):
        self.operators.add("del")
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def visit_Match(self, node):
        self.operators.add(self.name(node.op)+"=")
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)


    def visit_Del(self, node):
        self.operators.add("del")
        #print(self.name(node))
        self.__increase_total()
        self.generic_visit(node)

    def name(self,object):
        return object.__class__.__name__

    def visit_ClassDef(self, node):
        self.operators.add(node.__class__.__name__)
        #print(node.__class__.__name__)
        self.__increase_total()
        self.generic_visit(node)
    def visit_FunctionDef(self, node):
        self.operators.add(node.__class__.__name__)  
        #print(node.__class__.__name__)
        self.__increase_total()
        self.generic_visit(node)

        


class OperandCollector(ast.NodeVisitor):
    def __init__(self):
        self.operands = set()
        self.total_operands = []
        self.skip_next_name = False
        self.class_name = ""
        self.function_name = ""
        self.in_function_args = False
        self.in_class_bases = False
    
    def strip_docstrings(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and 
                isinstance(node.body[0], ast.Expr) and 
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:]
        
        for child in ast.iter_child_nodes(node):
            self.strip_docstrings(child)
    
    def visit(self, node):
        if isinstance(node, ast.Module):
            self.strip_docstrings(node)
        return super().visit(node)
    
    def add_operand(self, operand):
        self.operands.add(operand)
        self.total_operands.append(operand)
    
    def visit_ClassDef(self, node):
        old_class_name = self.class_name
        self.class_name = node.name
        
        if node.bases:
            self.in_class_bases = True
            for base in node.bases:
                self.visit(base)
            self.in_class_bases = False
        
        for decorator in node.decorator_list:
            self.visit(decorator)
        
        for stmt in node.body:
            self.visit(stmt)
        
        self.class_name = old_class_name
    
    def visit_FunctionDef(self, node):
        old_function_name = self.function_name
        self.function_name = node.name
        
        self.in_function_args = True
        self.visit(node.args)
        self.in_function_args = False
        
        for decorator in node.decorator_list:
            self.visit(decorator)
        
        if node.returns:
            self.visit(node.returns)
        
        for stmt in node.body:
            self.visit(stmt)
        
        self.function_name = old_function_name
    
    def visit_arguments(self, node):
        if self.in_function_args:
            for arg in node.args:
                self.add_operand(arg.arg)
                if arg.annotation:
                    self.visit(arg.annotation)
            
            for arg in getattr(node, 'posonlyargs', []):
                self.add_operand(arg.arg)
                if arg.annotation:
                    self.visit(arg.annotation)
            
            for arg in node.kwonlyargs:
                self.add_operand(arg.arg)
                if arg.annotation:
                    self.visit(arg.annotation)
            
            if node.vararg:
                self.add_operand(node.vararg.arg)
                if node.vararg.annotation:
                    self.visit(node.vararg.annotation)
            
            if node.kwarg:
                self.add_operand(node.kwarg.arg)
                if node.kwarg.annotation:
                    self.visit(node.kwarg.annotation)
            
            for default in node.defaults:
                self.visit(default)
            
            for default in node.kw_defaults:
                if default:
                    self.visit(default)
    
    def visit_Call(self, node):
        self.visit(node.func)
        
        old_skip = self.skip_next_name
        self.skip_next_name = True
        
        for arg in node.args:
            self.skip_next_name = False
            self.visit(arg)
        
        for keyword in node.keywords:
            self.skip_next_name = False
            self.visit(keyword.value)
        
        self.skip_next_name = old_skip
    
    def visit_Attribute(self, node):
        if not self.skip_next_name:
            if isinstance(node.value, ast.Name):
                if node.value.id == "self" and self.class_name:
                    operand = f"{self.class_name}.{node.attr}"
                    self.add_operand(operand)
                else:
                    operand = f"{node.value.id}.{node.attr}"
                    self.add_operand(operand)
            else:
                self.visit(node.value)
                self.add_operand(node.attr)
        else:
            self.visit(node.value)
    
    def visit_Name(self, node):
        if not self.skip_next_name:
            self.add_operand(node.id)
    
    def visit_Constant(self, node):
        if not self.skip_next_name:
            self.add_operand(node.value)
    
    def visit_JoinedStr(self, node):
        f_string_content = ""
        for value in node.values:
            if isinstance(value, ast.Constant):
                f_string_content += str(value.value)
            elif isinstance(value, ast.FormattedValue):
                f_string_content += "{}"
        
        self.add_operand(f_string_content)
        
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                self.visit(value.value)
                if value.format_spec:
                    self.visit(value.format_spec)

#Example usage

# file=open("Shape_Rectangle.py","r")

# tree=ast.parse(file.read())
# ##Halstead Metrics
# #Distinct operators (n1) and Distinct operands (n2)
# #Total operator (N1) and Total operands (N2) 

# visitor=OperatorCollector()
# visitor.visit(tree)
# print("Operators: ",visitor.operators)
# n1 = len(visitor.operators)
# N1=visitor.total_operators
# visitor=OperandCollector()
# #visitor.strip_docstrings(tree)
# visitor.visit(tree)
# n2 = len(visitor.operands)
# print("Unique operands: ",visitor.operands)
# N2= len(visitor.total_operands)
# print("All Operands: ",visitor.operands)

# print("Halstead Metrics---------")
# print("n1:",n1," n2:",n2)
# print("N1:",N1," N2:",N2)
# # program_vocabulary = n1+n2
# # print("Program Vocabulary:",program_vocabulary)
# # program_length = N1+N2
# # print("Program Length:",program_length)
# # estimated_program_length = n1*math.log2(n1)+n2*math.log2(n2)
# # print("Estimated Program Length:",estimated_program_length)
# # volume=program_length*math.log2(program_vocabulary)
# # print("Volume:",volume)
# # difficulty=(n1/2)*(N2/n2)
# # print("Difficulty:",difficulty)
# # effort = difficulty*volume
# # print("Effort:",effort)
# file=open("Square.py","r")

# tree=ast.parse(file.read())
# ##Halstead Metrics
# #Distinct operators (n1) and Distinct operands (n2)
# #Total operator (N1) and Total operands (N2) 

# visitor=OperatorCollector()
# visitor.visit(tree)
# print("Operators: ",visitor.operators)
# n1 = len(visitor.operators)
# N1=visitor.total_operators
# visitor=OperandCollector()
# #visitor.strip_docstrings(tree)
# visitor.visit(tree)
# n2 = len(visitor.operands)
# print("Unique operands: ",visitor.operands)
# N2= len(visitor.total_operands)
# print("All Operands: ",visitor.operands)

# print("Halstead Metrics---------")
# print("n1:",n1," n2:",n2)
# print("N1:",N1," N2:",N2)


