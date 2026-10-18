from fastapi import APIRouter
import wntr
import os
from schemas import NetworkGraph, NodeBase, EdgeBase

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NETWORK_FILE = os.path.abspath(os.path.join(BASE_DIR, "../../data/networks/Net3.inp"))

@router.get("/network", response_model=NetworkGraph)
def get_network():
    if not os.path.exists(NETWORK_FILE):
        return {"nodes": [], "edges": []}
        
    wn = wntr.network.WaterNetworkModel(NETWORK_FILE)
    
    nodes = []
    for name, node in wn.nodes():
        elev = getattr(node, 'elevation', 0.0)
        n_type = str(node.node_type)
        # Mark any negative-demand node as a supply source for the map legend.
        if getattr(node, 'base_demand', 0.0) is not None and getattr(node, 'base_demand', 0.0) < 0:
            n_type = "Reservoir"  # Main Supply Source
            
        nodes.append(NodeBase(
            id=name,
            x=node.coordinates[0],
            y=node.coordinates[1],
            type=n_type,
            elevation=float(elev) if elev is not None else 0.0
        ))
        
    edges = []
    for name, link in wn.links():
        edges.append(EdgeBase(
            id=name,
            source=link.start_node_name,
            target=link.end_node_name
        ))
        
    return NetworkGraph(nodes=nodes, edges=edges)
