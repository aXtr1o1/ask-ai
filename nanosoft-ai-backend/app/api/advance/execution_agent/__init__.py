"""
execution_agent — Public API

Re-exports the two entry-points used by external callers so that
   from app.api.advance.execution_agent import run_execution, build_formatting_context
continues to work regardless of internal restructuring.
"""
from app.api.advance.execution_agent.agent.agent          import run_execution          # noqa: F401
from app.api.advance.execution_agent.output.context_builder import build_formatting_context  # noqa: F401