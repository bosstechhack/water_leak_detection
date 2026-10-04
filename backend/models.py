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
