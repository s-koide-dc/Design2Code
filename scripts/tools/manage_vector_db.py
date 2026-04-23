# -*- coding: utf-8 -*-
import argparse
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.config.config_manager import ConfigManager
from src.code_synthesis.method_store import MethodStore
from src.vector_engine.vector_engine import VectorEngine

def harvest_analysis(config_manager):
    print("--- Harvesting from Analysis ---")
    from src.code_synthesis.method_harvester import MethodHarvester
    
    harvester = MethodHarvester(config_manager)
    analysis_path = os.path.join(os.getcwd(), 'cache', 'analysis_output')
    
    if os.path.exists(analysis_path):
        result = harvester.harvest_from_analysis(analysis_path)
        print(f"Result: {result}")
    else:
        print(f"Analysis path not found: {analysis_path}")

def seed_system(config_manager):
    print("--- Seeding System Methods ---")
    from scripts.seed_system_methods import seed_system_methods
    seed_system_methods(config_manager)

def rebuild_index(config_manager):
    print("--- Rebuilding Index (Vectorization) ---")
    # Initializing MethodStore with VectorEngine triggers re-indexing if needed
    # We force it by clearing vectors if requested, but for now just load & save
    vector_engine = VectorEngine()
    store = MethodStore(config_manager=config_manager, vector_engine=vector_engine)
    
    # Check consistency
    if store.items and (store.vectors is None or len(store.items) != len(store.vectors)):
        print("Detected mismatch/missing vectors. Re-indexing...")
        store.load() # Load logic handles re-indexing now
    else:
        print("Index seems consistent. Forcing re-save to be sure.")
        store.is_dirty = True
        store.save()
    
    print(f"Current Store Status: {len(store.methods)} methods.")

def main():
    parser = argparse.ArgumentParser(description="Manage the AI Method Store & Vector Database")
    parser.add_argument('action', choices=['harvest', 'seed', 'rebuild', 'all'], help="Action to perform")
    
    args = parser.parse_args()
    
    cm = ConfigManager()
    
    if args.action == 'seed' or args.action == 'all':
        seed_system(cm)
        
    if args.action == 'harvest' or args.action == 'all':
        harvest_analysis(cm)
        
    if args.action == 'rebuild' or args.action == 'all':
        rebuild_index(cm)

if __name__ == "__main__":
    main()
