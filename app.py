import os
import sys
import uuid
import shutil
from flask import Flask, render_template, request, url_for, redirect

# Check Graphviz
if shutil.which("dot") is None:
    raise RuntimeError("Graphviz not found. Install it")

from graphviz import Digraph

# Compiler modules
PACKAGE_DIR = os.path.dirname(__file__)
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from mini_c_compiler.lexer import simple_lex
from mini_c_compiler.parser import Parser
from mini_c_compiler.semantic_analyzer import SemanticAnalyzer

app = Flask(__name__)

# Ensure static/graphs exists
graphs_dir = os.path.join(app.root_path, 'static', 'graphs')
os.makedirs(graphs_dir, exist_ok=True)

# In-memory store
RUNS = {}

@app.route('/')
def index():
    run_id = request.args.get('run_id')
    data = RUNS.get(run_id) if run_id else None
    
    source = """int a;
a = 5 + 3 * (2 - 1);
if (a > 5) { a = a - 1; }
while (a < 10) { a = a + 1 ;}"""

    if data:
        source = data['source']
        
    return render_template('index.html', source=source, data=data, run_id=run_id)

@app.route('/compile', methods=['POST'])
def compile_code():
    source = request.form.get('source', '')
    
    tokens, lex_errors = simple_lex(source)
    parser = Parser(tokens)
    root = parser.parse()
    
    combined = []
    for le in lex_errors:
        combined.append({
            "type": "Lexical Error",
            "message": le.message,
            "line": le.line,
            "column": le.column,
        })
        
    for pe in parser.get_errors():
        combined.append({
            "type": "Parse Error",
            "message": pe.message,
            "line": pe.line,
            "column": pe.column,
        })
        
    corrected_source = parser.get_corrected_source()
    
    # Semantic Analysis
    semantic_success = False
    symbol_table_str = ""
    semantic_errors = []
    
    if root and len(lex_errors) == 0 and len(parser.get_errors()) == 0:
        semantic_analyzer = SemanticAnalyzer()
        semantic_success, semantic_errors_list = semantic_analyzer.analyze(root)
        
        for se in semantic_errors_list:
            combined.append({
                "type": "Semantic Error",
                "message": se.message,
                "line": se.line,
                "column": se.column,
            })
            semantic_errors.append(se.message)
        
        symbol_table = semantic_analyzer.get_symbol_table()
        symbol_table_str = semantic_analyzer.print_symbol_table()
    
    # Only generate AST if there are NO errors
    graph_url = None
    total_steps = 0
    if root and len(lex_errors) == 0 and len(parser.get_errors()) == 0 and semantic_success:
        graph_id = str(uuid.uuid4())
        graph_filename = f'tree_{graph_id}.svg'
        graph_path = os.path.join(graphs_dir, graph_filename)
        
        dot = Digraph(format='svg')
        dot.attr(bgcolor='transparent', rankdir='TB')
        dot.attr('node', shape='box', style='filled,solid', fillcolor='#0a0a0a', color='#eaff00', fontcolor='#eaff00', fontname='JetBrains Mono', penwidth='2', fontsize='16', margin='0.2')
        dot.attr('edge', color='#ff003c', penwidth='2')
        
        step_counter = 0
        def add_nodes(node, parent=None):
            nonlocal step_counter
            if node is None: return
            node_id = str(id(node))
            
            step_counter += 1
            # Give leaf nodes an ellipse shape to differentiate them
            node_shape = 'ellipse' if not node.children else 'box'
            dot.node(node_id, node.name, id=f"step_{step_counter}", shape=node_shape)
            
            if parent:
                step_counter += 1
                dot.edge(parent, node_id, id=f"step_{step_counter}")
                
            for child in node.children:
                add_nodes(child, node_id)
                
        add_nodes(root)
        total_steps = step_counter
        try:
            dot.render(graph_path.replace('.svg', ''), format='svg')
            graph_url = url_for('static', filename=f'graphs/{graph_filename}')
        except Exception as e:
            print("Graphviz error:", e)
            graph_url = None
            total_steps = 0
            
    run_id = str(uuid.uuid4())
    RUNS[run_id] = {
        "source": source,
        "tokens": tokens,
        "errors": combined,
        "corrected_source": corrected_source,
        "graph_url": graph_url,
        "total_steps": total_steps if root else 0,
        "semantic_success": semantic_success,
        "symbol_table": symbol_table_str,
    }
    
    return redirect(url_for('index', run_id=run_id))

@app.route('/ast/<run_id>')
def ast_view(run_id):
    if run_id not in RUNS or not RUNS[run_id]['graph_url']:
        return redirect(url_for('index'))
    return render_template('ast.html', graph_url=RUNS[run_id]['graph_url'], run_id=run_id, total_steps=RUNS[run_id].get('total_steps', 0))

@app.route('/semantic/<run_id>')
def semantic_view(run_id):
    if run_id not in RUNS:
        return redirect(url_for('index'))
    data = RUNS[run_id]
    return render_template('semantic.html', 
                          symbol_table=data.get('symbol_table', ''),
                          errors=data.get('errors', []),
                          run_id=run_id,
                          semantic_success=data.get('semantic_success', False))



if __name__ == '__main__':
    app.run(debug=True, port=5001)
