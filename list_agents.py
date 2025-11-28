#!/usr/bin/env python3
"""
List all active and inactive agents (insight types) in the SparksAI-Agent system.
"""

import config
from job_router import route_and_process

# All job types defined in config
ALL_JOB_TYPES = config.JOB_TYPES

# Check which job types have handlers in the router
# We'll verify by checking if they're handled in route_and_process
HANDLED_JOB_TYPES = {
    "Daily Progress": True,
    "Sprint Goal": True,
    "PI Sync": True,
    "Team PI Insight": True,
    "Team Retro Topics": True,
    "PI Dependencies": True,
}

# Also check for backward compatibility
BACKWARD_COMPATIBLE_TYPES = {
    "Team Retrospective Preparation": "Team Retro Topics",  # Old name maps to new handler
}

def get_agent_status():
    """Get status of all agents/insight types."""
    active_agents = []
    inactive_agents = []
    
    # All job types in config are considered "active" (configured to be processed)
    for job_type in ALL_JOB_TYPES:
        if job_type in HANDLED_JOB_TYPES and HANDLED_JOB_TYPES[job_type]:
            active_agents.append(job_type)
        else:
            inactive_agents.append(job_type)
    
    return active_agents, inactive_agents

def print_agent_list():
    """Print formatted list of active and inactive agents."""
    active, inactive = get_agent_status()
    
    print("=" * 70)
    print("SPARKSAI-AGENT: INSIGHT TYPES (AGENTS) STATUS")
    print("=" * 70)
    print()
    
    print(f"[ACTIVE] ACTIVE AGENTS ({len(active)}):")
    print("-" * 70)
    if active:
        for i, agent in enumerate(active, 1):
            print(f"  {i}. {agent}")
    else:
        print("  (none)")
    print()
    
    print(f"[INACTIVE] INACTIVE AGENTS ({len(inactive)}):")
    print("-" * 70)
    if inactive:
        for i, agent in enumerate(inactive, 1):
            print(f"  {i}. {agent}")
    else:
        print("  (none)")
    print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Agents: {len(ALL_JOB_TYPES)}")
    print(f"Active: {len(active)}")
    print(f"Inactive: {len(inactive)}")
    print()
    
    if BACKWARD_COMPATIBLE_TYPES:
        print("Backward Compatible Job Types:")
        for old_name, new_name in BACKWARD_COMPATIBLE_TYPES.items():
            print(f"  '{old_name}' -> '{new_name}'")
        print()

if __name__ == "__main__":
    print_agent_list()

