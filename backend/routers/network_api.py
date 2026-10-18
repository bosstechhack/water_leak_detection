import json
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import wntr

from catalog import DATA_DIR, NETWORK_FILES, describe
from database import get_db
from models import ScenarioRecord
from schemas import EdgeBase, NetworkGraph, NetworkInfo, NodeBase, ScenarioInfo

router = APIRouter()

NETWORK_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../data/networks"))
NETWORK_NAMES = {"net1": "Net1 (small, pump + tank)", "net2": "Net2 (35 junctions, tank only)",
                 "net3": "Net3 (benchmark, 92 junctions)"}


def _network_path(network: str):
    filename = NETWORK_FILES.get(network)
    if filename is None:
        raise HTTPException(status_code=404, detail=f"Unknown network: {network}")
    return os.path.join(NETWORK_DIR, filename)


@router.get("/networks", response_model=List[NetworkInfo])
def list_networks(db: Session = Depends(get_db)):
    infos = []
    for network in NETWORK_FILES:
        if not os.path.isdir(os.path.join(DATA_DIR, network)):
            continue
        wn = wntr.network.WaterNetworkModel(_network_path(network))
        count = db.query(ScenarioRecord).filter(ScenarioRecord.network == network).count()
        infos.append(NetworkInfo(id=network, name=NETWORK_NAMES.get(network, network),
                                 junctions=len(wn.junction_name_list), scenarios=count))
    return infos


@router.get("/scenarios", response_model=List[ScenarioInfo])
def list_scenarios(network: str = "net3", db: Session = Depends(get_db)):
    rows = db.query(ScenarioRecord).filter(ScenarioRecord.network == network).order_by(ScenarioRecord.id).all()
    return [ScenarioInfo(id=r.id, network=r.network, name=r.name, group=r.scenario_group,
                         event_class=r.event_class, truth_nodes=[t for t in r.truth_nodes.split("|") if t],
                         params=json.loads(r.params_json or "{}"))
            for r in rows]


@router.get("/network", response_model=NetworkGraph)
def get_network(network: str = "net3"):
    path = _network_path(network)
    if not os.path.exists(path):
        return {"nodes": [], "edges": []}
    wn = wntr.network.WaterNetworkModel(path)

    nodes = []
    for name, node in wn.nodes():
        elev = getattr(node, "elevation", 0.0)
        n_type = str(node.node_type)
        # A junction with negative demand injects water (supply source in Net2); show it as a source.
        demands = getattr(node, "demand_timeseries_list", [])
        if demands and sum(d.base_value for d in demands) < 0:
            n_type = "Reservoir"
        nodes.append(NodeBase(id=name, x=node.coordinates[0], y=node.coordinates[1], type=n_type,
                              elevation=float(elev) if elev is not None else 0.0))

    edges = [EdgeBase(id=name, source=link.start_node_name, target=link.end_node_name)
             for name, link in wn.links()]
    return NetworkGraph(nodes=nodes, edges=edges)
