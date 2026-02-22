"""Test graph compilation."""
import time
t0 = time.time()
from history_tales_agent.graph import compile_graph
print(f"Import took {time.time()-t0:.1f}s")
t1 = time.time()
g = compile_graph()
print(f"Compile took {time.time()-t1:.1f}s")
nodes = list(g.get_graph().nodes.keys())
print(f"Nodes ({len(nodes)}): {nodes}")
