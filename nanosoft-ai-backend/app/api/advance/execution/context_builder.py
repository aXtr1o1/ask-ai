"""
Context Builder — formats the Execution Agent's raw output into a clean context for the Formatting Agent.
"""
from app.api.advance.execution.schemas import ExecutionResult

def build_formatting_context(execution_result: ExecutionResult) -> dict:
    """
    Builds the context needed for the Formatting Agent.
    
    Returns a dictionary containing:
    1. The planned steps (what the LLM decided to do).
    2. The final answer (computed result).
    """
    queue = execution_result.get("queue", [])
    step_results = execution_result.get("step_results", {})
    
    # 1. Get the final answer
    last_step_key = f"step_{len(queue) - 1}" if queue else None
    final_output = step_results.get(last_step_key, {}) if last_step_key else {}
    final_answer = final_output.get("final_value", final_output)
    
    # 2. Extract just the steps the LLM decided (the plan), without the intermediate outputs
    planned_steps = []
    for step in queue:
        planned_steps.append({
            "step": step["step"],
            "tool": step["tool"],
            "args": step.get("args", {})
        })
        
    return {
        "planned_steps": planned_steps,
        "final_answer": final_answer
    }
