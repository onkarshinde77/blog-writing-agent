"""
Blog Writing Agent - Main Entry Point & Streamlit UI
"""
import streamlit as st
import os
import sys

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.config import CONFIG
from src.graph import app

 
# Main Execution Function (Programmatic access)
def run(topic: str) -> dict:
    """Execute the blog writing workflow for a given topic synchronously."""
    out = app.invoke(
        {
            "topic": topic,
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "final": "",
        },
        config=CONFIG
    )
    return out

 
# Streamlit UI
st.set_page_config(
    page_title="Blog Writing Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern loading states
st.markdown("""
<style>
    .status-running { color: #f39c12; font-weight: bold; }
    .status-completed { color: #2ecc71; font-weight: bold; }
    .status-waiting { color: #7f8c8d; }
    .status-skipped { color: #95a5a6; text-decoration: line-through; }
    .node-box {
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 5px;
        background-color: #1e1e2e;
        border-left: 4px solid #333;
    }
    .node-box-running { border-left-color: #f39c12; }
    .node-box-completed { border-left-color: #2ecc71; }
</style>
""", unsafe_allow_html=True)

st.title("📝 AI Blog Writing Agent")
st.markdown("""
Welcome to the AI-powered Blog Writing Agent! 
This agent uses a multi-agent workflow to research and write a comprehensive blog post based on your topic.
""")

with st.sidebar:
    st.header("Settings")
    st.info("The agent will automatically determine if research is needed and coordinate multiple workers to write sections.")

# UI Input for Blog Topic
topic_input = st.text_input("Enter a topic for the blog post:", placeholder="e.g., The Future of Artificial Intelligence")

if st.button("Generate Blog Post", type="primary"):
    if not topic_input.strip():
        st.warning("Please enter a topic to continue.")
    else:
        st.divider()
        st.subheader("Workflow Progress")
        
        # Define UI containers for each node
        ui_nodes = {
            "router": {"label": "Analyzing topic & routing", "icon": "🧭"},
            "research": {"label": "Researching web for evidence", "icon": "🔍"},
            "orchestrator": {"label": "Orchestrating blog plan", "icon": "📋"},
            "workers": {"label": "Workers writing sections", "icon": "✍️"},
            "merge_content": {"label": "Merging sections", "icon": "🧩"},
            "decide_images": {"label": "Planning AI images", "icon": "🧠"},
            "generate_and_place_images": {"label": "Generating images & finishing", "icon": "🖼️"}
        }
        
        # Create a container for every node up front
        containers = {}
        for key, config in ui_nodes.items():
            containers[key] = st.empty()
            # Set initial waiting state
            containers[key].markdown(f"<div class='node-box'>⏳ &nbsp; **{config['icon']} {config['label']}** - <span class='status-waiting'>Waiting...</span></div>", unsafe_allow_html=True)
            
        progress_bar = st.progress(0)
        
        # We'll use an expander to show detailed logs at the bottom
        with st.expander("Detailed Event Logs", expanded=False):
            log_container = st.empty()
            logs = []
            def append_log(msg):
                logs.append(msg)
                log_container.markdown("\n".join(f"- {log}" for log in logs))
        
        final_blog_container = st.container()
        
        initial_state = {
            "topic": topic_input,
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "final": "",
        }
        
        try:
            final_state = None
            workers_completed = 0
            
            # Start UI state before stream starts
            containers["router"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['router']['icon']} {ui_nodes['router']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)
            progress_bar.progress(5)
            
            # Using langgraph stream to get real-time updates from nodes
            for event in app.stream(initial_state, config=CONFIG, subgraphs=True):
                # When subgraphs=True, it yields ((namespace), chunk)
                # chunk is typically a dict mapping nodeName -> state updates
                chunk = event[1]
                for key, value in chunk.items():
                    node_name = key
                    append_log(f"✅ **{node_name}** executed successfully.")
                    
                    if node_name == "router":
                        progress_bar.progress(20)
                        # Mark router as complete
                        containers["router"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['router']['icon']} {ui_nodes['router']['label']}** - <span class='status-completed'>Completed</span></div>", unsafe_allow_html=True)
                        
                        # Decide what runs next
                        if value.get("needs_research"):
                            append_log("Router decided research IS needed.")
                            containers["research"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['research']['icon']} {ui_nodes['research']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)
                        else:
                            append_log("Router decided research is NOT needed.")
                            containers["research"].markdown(f"<div class='node-box'>⏭️ &nbsp; **{ui_nodes['research']['icon']} {ui_nodes['research']['label']}** - <span class='status-skipped'>Skipped (Not needed)</span></div>", unsafe_allow_html=True)
                            containers["orchestrator"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['orchestrator']['icon']} {ui_nodes['orchestrator']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)
                            
                    elif node_name == "research":
                        progress_bar.progress(40)
                        found = len(value.get('evidence', []))
                        containers["research"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['research']['icon']} {ui_nodes['research']['label']}** - <span class='status-completed'>Completed (Found {found} items)</span></div>", unsafe_allow_html=True)
                        # Research is followed by orchestrator
                        containers["orchestrator"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['orchestrator']['icon']} {ui_nodes['orchestrator']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)
                            
                    elif node_name == "orchestrator":
                        progress_bar.progress(60)
                        plan = value.get("plan")
                        num_sections = len(plan.tasks) if plan and hasattr(plan, "tasks") else "all"
                        containers["orchestrator"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['orchestrator']['icon']} {ui_nodes['orchestrator']['label']}** - <span class='status-completed'>Completed ({num_sections} sections planned)</span></div>", unsafe_allow_html=True)
                        # Orchestrator is followed by workers
                        containers["workers"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['workers']['icon']} {ui_nodes['workers']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)
                            
                    elif node_name == "workers":
                        workers_completed += 1
                        containers["workers"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['workers']['icon']} {ui_nodes['workers']['label']}** - <span class='status-running'>Running... ({workers_completed} section(s) done)</span></div>", unsafe_allow_html=True)
                        if workers_completed == 1:
                             progress_bar.progress(70) 
                             
                    elif node_name == "merge_content":
                        progress_bar.progress(80)
                        containers["workers"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['workers']['icon']} {ui_nodes['workers']['label']}** - <span class='status-completed'>Completed</span></div>", unsafe_allow_html=True)
                        containers["merge_content"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['merge_content']['icon']} {ui_nodes['merge_content']['label']}** - <span class='status-completed'>Completed</span></div>", unsafe_allow_html=True)
                        containers["decide_images"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['decide_images']['icon']} {ui_nodes['decide_images']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)

                    elif node_name == "decide_images":
                        progress_bar.progress(90)
                        specs = len(value.get("image_specs", []))
                        containers["decide_images"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['decide_images']['icon']} {ui_nodes['decide_images']['label']}** - <span class='status-completed'>Completed ({specs} images)</span></div>", unsafe_allow_html=True)
                        containers["generate_and_place_images"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['generate_and_place_images']['icon']} {ui_nodes['generate_and_place_images']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)

                    elif node_name == "generate_and_place_images":
                        progress_bar.progress(100)
                        containers["generate_and_place_images"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['generate_and_place_images']['icon']} {ui_nodes['generate_and_place_images']['label']}** - <span class='status-completed'>Completed</span></div>", unsafe_allow_html=True)
                        final_state = value

            if final_state is None and 'out' in locals():
                 pass
            elif final_state:
                final_content = final_state.get("final", "")
                with final_blog_container:
                    st.success("🎉 Blog generation completed successfully!")
                    st.markdown("---")
                    st.markdown("## Generated Blog Post")
                    st.markdown(final_content)
                    
                    st.download_button(
                        label="⬇️ Download Markdown File",
                        data=final_content,
                        file_name=f"{topic_input.replace(' ', '_').lower()}.md",
                        mime="text/markdown"
                    )
            else:
                 st.error("Workflow completed but no final state was retrieved.")

        except Exception as e:
            st.error(f"An error occurred during workflow execution: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
