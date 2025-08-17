import ast


program = '''
def Hello(i=0):
	print("Hello World: ", i)
Hello(1)
'''

tree=ast.parse(program)
print(ast.dump(tree, indent=1))