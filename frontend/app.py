import streamlit as st
import sys
import os

# Add the parent directory to sys.path to allow imports from src and main
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import CONFIG
from src.graph import app

st.set_page_config(
    page_title="Blog Writing Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📝 AI Blog Writing Agent")
st.markdown("""
Welcome to the AI-powered Blog Writing Agent! 
This agent uses a multi-agent workflow to research and write a comprehensive blog post based on your topic.
""")

with st.sidebar:
    st.header("Settings")
    st.info("The agent will automatically determine if research is needed and coordinate multiple workers to write sections.")

topic = st.text_input("Enter a topic for the blog post:", placeholder="e.g., The State of Multimodal LLMs in 2026")

if st.button("Generate Blog Post", type="primary"):
    if not topic.strip():
        st.warning("Please enter a topic to continue.")
    else:
        st.divider()
        st.subheader("Workflow Progress")
        
        # Create a container for the status updates
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        # We'll use an expander to show detailed logs
        with st.expander("Detailed Workflow Execution", expanded=True):
            log_container = st.empty()
            logs = []
            
            def append_log(msg):
                logs.append(msg)
                log_container.markdown("\n".join(f"- {log}" for log in logs))
        
        # Output container for the final blog
        final_blog_container = st.container()
        
        # Initial state for the graph
        initial_state = {
            "topic": topic,
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "final": "",
        }
        
        try:
            status_text.write("Starting blog generation workflow...")
            final_state = None
            
            # Using stream to get real-time updates from nodes
            for output in app.stream(initial_state, config=CONFIG):
                for key, value in output.items():
                    # Update status based on the node executing
                    node_name = key
                    append_log(f"**{node_name}** completed.")
                    
                    if node_name == "router":
                        progress_bar.progress(10)
                        if value.get("needs_research"):
                            status_text.write("Router decided research is needed. Researching...")
                        else:
                            status_text.write("Router decided research is NOT needed. Moving to orchestration...")
                            
                    elif node_name == "research":
                        progress_bar.progress(30)
                        status_text.write("Research completed. Orchestrating blog plan...")
                        if value.get("evidence"):
                            append_log(f"Found {len(value.get('evidence', []))} evidence items.")
                            
                    elif node_name == "orchestrator":
                        progress_bar.progress(50)
                        status_text.write("Blog plan created! Writing sections...")
                        plan = value.get("plan")
                        if plan and hasattr(plan, "tasks"): # Assuming plan has tasks attribute
                            append_log(f"Created plan with {len(plan.tasks)} sections.")
                            
                    elif node_name == "workers":
                        progress_bar.progress(80)
                        status_text.write("Workers generated sections. Compiling final blog...")
                        sections = value.get("sections", [])
                        append_log(f"Generated {len(sections)} sections.")
                        
                    elif node_name == "reducer":
                        progress_bar.progress(100)
                        status_text.write("Blog generation finished!")
                        final_state = value

            if final_state is None and 'out' in locals():
                 # fallback if the loop behaved differently
                 pass
            elif final_state:
                final_content = final_state.get("final", "")
                
                with final_blog_container:
                    st.success("✅ Blog generation completed successfully!")
                    st.markdown("---")
                    st.markdown("## Generated Blog Post")
                    st.markdown(final_content)
                    
                    st.download_button(
                        label="Download Markdown File",
                        data=final_content,
                        file_name=f"{topic.replace(' ', '_').lower()}.md",
                        mime="text/markdown"
                    )
            else:
                 st.error("Workflow completed but no final state was retrieved.")

        except Exception as e:
            st.error(f"An error occurred during workflow execution: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
