from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    scenario_name = Column(String, index=True)
    is_baseline = Column(Boolean, default=False)
    leak_node = Column(String, nullable=True)
    # We store the path to the CSV instead of ingesting everything for Sem 1 simplicity
    pressures_csv_path = Column(String)
    flows_csv_path = Column(String)


class ScenarioRecord(Base):
    """One simulated scenario (metadata only; time series stay in CSV files)."""
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True, index=True)
    network = Column(String, index=True)
    name = Column(String)
    scenario_group = Column(String, index=True)
    event_class = Column(String, index=True)
    truth_nodes = Column(String, default="")
    params_json = Column(String, default="{}")
    csv_dir = Column(String)
