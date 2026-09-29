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


# ============================================================================
# Main Execution Function (Programmatic access)
# ============================================================================
def run(topic: str) -> dict:
    """Execute the blog writing workflow for a given topic synchronously."""
    import uuid
    thread_id = str(uuid.uuid4())
    run_config = {"configurable": {"thread_id": thread_id}, "run_name": "blog-writing-agent"}
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
            "workflow_id": thread_id,
        },
        config=run_config
    )
    return out

# ============================================================================
# Streamlit UI
# ============================================================================
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
    st.title("History")    
    st.divider()
    if st.button("➕ New Blog", use_container_width=True, type="primary"):
        st.session_state.viewing_history = False
        
    st.header("Previous Blogs")
    
    # Fetch all threads from SQLite
    completed_blogs = []
    seen_topics = set()
    # Internal placeholder thread IDs that should never appear in history
    INTERNAL_THREAD_IDS = {"blog-1", "__default__"}
    import sqlite3
    try:
        conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT DISTINCT thread_id FROM checkpoints")
        thread_ids = [row[0] for row in c.fetchall()]
        conn.close()
        for tid in thread_ids:
            # Skip internal/placeholder threads
            if tid in INTERNAL_THREAD_IDS:
                continue
            states = list(app.get_state_history({"configurable": {"thread_id": tid}}))
            for state in states:
                # Only show threads that have a completed final blog
                if not state.next and state.values.get("final"):
                    s_id = state.config.get("configurable", {}).get("checkpoint_id", "")
                    if s_id not in seen_topics:
                        seen_topics.add(s_id)
                        completed_blogs.append(state)
    except Exception:
        pass
                
    if not completed_blogs:
        st.info("No history yet.")
    else:
        for idx, state in enumerate(completed_blogs):
            h_topic = state.values.get("topic", f"Blog {idx+1}")
            # Truncate topic logic for sidebar
            short_topic = (h_topic[:25] + '...') if len(h_topic) > 25 else h_topic
            
            if st.button(f"💬 {short_topic}", key=f"hist_btn_{idx}_{state.config.get('configurable', {}).get('checkpoint_id', idx)}", use_container_width=True):
                st.session_state.viewing_history = True
                st.session_state.current_view_blog = state.values.get("final", "")
                st.session_state.current_view_topic = h_topic

if st.session_state.get("viewing_history", False):
    h_topic = st.session_state.get("current_view_topic", "Previous Blog")
    h_final = st.session_state.get("current_view_blog", "")
    
    st.subheader(f"📚 {h_topic}")
    st.markdown(h_final)
    st.download_button(
        label="⬇️ Download Markdown File",
        data=h_final,
        file_name=f"{h_topic.replace(' ', '_').lower()}.md",
        mime="text/markdown"
    )
    st.stop()

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
            "reducer": {"label": "Compiling final blog", "icon": "✨"}
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
            "workflow_id": thread_id,
        }
        
        try:
            final_state = None
            workers_completed = 0
            
            # Start UI state before stream starts
            containers["router"].markdown(f"<div class='node-box node-box-running'>🔄 &nbsp; **{ui_nodes['router']['icon']} {ui_nodes['router']['label']}** - <span class='status-running'>Running...</span></div>", unsafe_allow_html=True)
            progress_bar.progress(5)
            
            import uuid
            current_thread_id = str(uuid.uuid4())
            run_config = {"configurable": {"thread_id": current_thread_id}, "run_name": "blog-writing-agent"}
            initial_state["workflow_id"] = current_thread_id
            st.session_state.active_workflow_id = current_thread_id
            
            # Using langgraph stream to get real-time updates from nodes
            for output in app.stream(initial_state, config=run_config):
                for key, value in output.items():
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
                             progress_bar.progress(80) 
                             
                    elif node_name == "reducer":
                        progress_bar.progress(100)
                        containers["workers"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['workers']['icon']} {ui_nodes['workers']['label']}** - <span class='status-completed'>Completed</span></div>", unsafe_allow_html=True)
                        containers["reducer"].markdown(f"<div class='node-box node-box-completed'>✅ &nbsp; **{ui_nodes['reducer']['icon']} {ui_nodes['reducer']['label']}** - <span class='status-completed'>Completed</span></div>", unsafe_allow_html=True)
                        final_state = value

            if final_state is None:
                 st.session_state.active_workflow_id = current_thread_id
                 st.info("Blog generated. Continue in the approval dashboard below.")
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

# Protect approval/publishing actions when a deployment configures a dashboard password.
publishing_password = os.getenv("PUBLISHING_UI_PASSWORD")
if publishing_password and not st.session_state.get("publishing_authenticated"):
    st.subheader("Publishing dashboard sign in")
    supplied_password = st.text_input("Publishing password", type="password", key="publishing_password_input")
    if st.button("Sign in to publishing dashboard") and __import__("hmac").compare_digest(supplied_password, publishing_password):
        st.session_state.publishing_authenticated = True
        st.rerun()
    st.info("Sign in to review and publish saved articles.")
    st.stop()

# Resumable approval dashboard. LangGraph's interrupt payload is persisted with the stable thread ID.
active_id = st.session_state.get("active_workflow_id")
if active_id:
    from langgraph.types import Command
    active_config = {"configurable": {"thread_id": active_id}}
    try:
        snapshot = app.get_state(active_config)
        pending = next((item.value for task in snapshot.tasks for item in task.interrupts), None)
        if pending:
            st.divider()
            if pending.get("type") == "blog_review":
                st.subheader("Blog review")
                st.json(pending.get("review") or {})
                current_blog = pending.get("blog") or {}
                edited_title = st.text_input("Title", current_blog.get("title", ""), key="approval_title")
                edited_content = st.text_area("Approved blog (Markdown)", current_blog.get("content", ""), height=350, key="approval_content")
                c1, c2, c3 = st.columns(3)
                with c1:
                    approve_blog = st.button("Approve", key="approve_blog")
                with c2:
                    revise_blog = st.button("Revise", key="revise_blog")
                with c3:
                    reject_blog = st.button("Reject", key="reject_blog")
                platforms = st.multiselect("Publish to", ["wordpress", "devto", "ghost"], default=["wordpress", "devto", "ghost"], format_func=lambda p: {"wordpress": "WordPress.com", "devto": "DEV.to", "ghost": "Ghost"}[p])
                feedback = st.text_input("Revision notes", key="blog_feedback")
                if approve_blog:
                    app.invoke(Command(resume={"action": "approve", "platforms": platforms}), config=active_config)
                    st.rerun()
                if revise_blog:
                    app.invoke(Command(resume={"action": "edit", "blog": {**current_blog, "title": edited_title, "content": edited_content}}), config=active_config)
                    st.rerun()
                if reject_blog:
                    app.invoke(Command(resume={"action": "reject", "feedback": feedback}), config=active_config)
                    st.rerun()
            elif pending.get("type") == "linkedin_approval":
                st.subheader("LinkedIn post approval")
                draft = pending.get("draft") or {}
                st.caption("Primary article: " + str(pending.get("primary_url", "")))
                st.caption("Hashtags: " + " ".join("#" + str(tag).lstrip("#") for tag in draft.get("hashtags", [])))
                st.json(pending.get("platform_links", {}))
                linkedin_text = st.text_area("LinkedIn post", draft.get("text", ""), height=220, key="linkedin_text")
                c1, c2 = st.columns(2)
                with c1:
                    approve_linkedin = st.button("Approve & Publish", key="approve_linkedin")
                with c2:
                    reject_linkedin = st.button("Reject LinkedIn post", key="reject_linkedin")
                if approve_linkedin:
                    app.invoke(Command(resume={"action": "approve", "text": linkedin_text}), config=active_config)
                    st.rerun()
                if reject_linkedin:
                    app.invoke(Command(resume={"action": "reject"}), config=active_config)
                    st.rerun()
                if linkedin_text != draft.get("text", ""):
                    if st.button("Save edit for review", key="save_linkedin_edit"):
                        app.invoke(Command(resume={"action": "edit", "text": linkedin_text}), config=active_config)
                        st.rerun()
        elif snapshot.values.get("final"):
            st.subheader("Publishing results")
            st.markdown(snapshot.values.get("final", ""))
            result = snapshot.values.get("final_result") or {"platforms": snapshot.values.get("published_links", {}), "linkedin": snapshot.values.get("linkedin_result"), "successful_urls": snapshot.values.get("all_published_urls", []), "failed_platforms": snapshot.values.get("failed_platforms", [])}
            st.json(result)
            st.text_area("Copy all links", "\n".join(result.get("successful_urls", [])), height=90, key="published_links_copy")
    except Exception as exc:
        st.warning("Workflow status is not available yet.")
