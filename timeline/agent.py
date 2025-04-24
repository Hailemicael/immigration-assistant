import json
import os
from typing import Dict, Optional, Any
import psycopg2
from psycopg2.extras import Json as PsycopgJson
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END

class TimelineAgent(Runnable):
    def __init__(self, llm, verbose, db_config=None, sql_file_path="timeline.sql"):
        self.llm = llm
        self.verbose = verbose
        self.db_config = db_config
        self.db_connection = None
        self.sql_file_path = sql_file_path
        
        # Initialize database connection if config is provided
        if self.db_config:
            self._init_db_connection()
            if self.db_connection:
                self._init_db_schema()
    
    def _init_db_connection(self):
        """Initialize the database connection"""
        try:
            self.db_connection = psycopg2.connect(**self.db_config)
            if self.verbose:
                print(f"[DEBUG - TimelineAgent] Database connection established")
        except Exception as e:
            print(f"[ERROR - TimelineAgent] Database connection failed: {str(e)}")
            self.db_connection = None
    
    def _init_db_schema(self):
        """Initialize database schema using the SQL file"""
        if not os.path.exists(self.sql_file_path):
            print(f"[ERROR - TimelineAgent] SQL file not found: {self.sql_file_path}")
            return
        
        try:
            # Read the SQL file
            with open(self.sql_file_path, 'r') as sql_file:
                sql_script = sql_file.read()
            
            # Execute the SQL script
            with self.db_connection.cursor() as cursor:
                cursor.execute(sql_script)
            
            # Commit the transaction
            self.db_connection.commit()
            
            if self.verbose:
                print(f"[DEBUG - TimelineAgent] Database schema initialized from: {self.sql_file_path}")
        
        except Exception as e:
            print(f"[ERROR - TimelineAgent] Database schema initialization failed: {str(e)}")
            if self.db_connection:
                self.db_connection.rollback()
    
    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        verbose = state.get("verbose", self.verbose)
        if verbose:
            print(f"\n[DEBUG - TimelineAgent] Processing forms: {state.get('forms', [])}")
        
        if not state.get("forms"):
            if verbose:
                print(f"[DEBUG - TimelineAgent] No forms found, skipping")
            return {}
        
        timeline_info = [f"{form}: 3–6 months processing" for form in state.get("forms", [])]
        
        if verbose:
            print(f"[DEBUG - TimelineAgent] Generated timeline info: {timeline_info}")
        
        # Update history
        history = state.get("history", [])
        history.append({
            "agent": "TimelineAgent",
            "generated_timelines": len(timeline_info)
        })
        
        # Save to database if connection is available
        if self.db_connection and not self.db_connection.closed:
            try:
                with self.db_connection.cursor() as cursor:
                    # Get history entry
                    history_entry = history[-1]
                    generated_timelines = history_entry.get("generated_timelines", 0)
                    
                    # Use the database function to save the timeline data
                    cursor.execute(
                        """
                        SELECT timeline.save_agent_timeline(
                            %s,  -- agent_name_param
                            %s,  -- generated_items_param
                            %s,  -- state_data_param
                            %s   -- timeline_entries_param
                        )
                        """,
                        (
                            "TimelineAgent", 
                            generated_timelines,
                            PsycopgJson(state),
                            PsycopgJson(timeline_info)
                        )
                    )
                    
                    # Commit the transaction
                    self.db_connection.commit()
                    
                    if verbose:
                        print(f"[DEBUG - TimelineAgent] Successfully saved data to database")
                    
            except Exception as e:
                print(f"[ERROR - TimelineAgent] Database save failed: {str(e)}")
                if self.db_connection:
                    self.db_connection.rollback()
        
        return {
            "timeline": timeline_info,
            "history": history
        }
    
    def route_after_timeline(self, state: Dict) -> str:
        if state.get("verbose", self.verbose):
            print(f"[📆 Timeline Routing] → Generation Stage: {state.get('generation_stage')}")
        return END
        # return "ReasoningAgent" if state.get("generation_stage") == "initial" else END

    def close(self):
        """Close the database connection"""
        if self.db_connection and not self.db_connection.closed:
            self.db_connection.close()
            if self.verbose:
                print(f"[DEBUG - TimelineAgent] Database connection closed")
