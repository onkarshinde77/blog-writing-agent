import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { ArrowRight, BookOpen, Check, CircleHelp, LoaderCircle, LockKeyhole, Menu, Plus, Send, Sparkles, Trash2, X } from "lucide-react";
import { api, base } from "./api.js";

const MarkdownRenderer = lazy(() => import("./Markdown.jsx"));
const LENGTHS = ["Short · about 600 words", "Standard · about 1,000 words", "In-depth · about 1,600 words"];
const cx = (...items) => items.filter(Boolean).join(" ");
const titleOf = (blog) => blog?.title || blog?.topic || "Untitled article";
const pretty = (value) => (value || "draft").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const modelLabel = (id, options) => options.find((item) => item.id === id)?.label || id || "Qwen 3.5 · 4B";

function SignIn({ onLogin }) {
  const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event) { event.preventDefault(); setBusy(true); try { await onLogin(password); } catch (problem) { setError(problem.message); } finally { setBusy(false); } }
  return <div className="login-backdrop"><form className="login-box" onSubmit={submit}><div className="brand-mark"><Sparkles size={20} /></div><div className="kicker">ONKAR AI · EDITORIAL STUDIO</div><h2>Welcome back.</h2><p>Sign in to continue to your workspace.</p><label>Studio password<input autoFocus type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>{error && <div className="error-text">{error}</div>}<button className="primary-button" disabled={busy || !password}>{busy ? <LoaderCircle className="spin" size={16} /> : "Sign in"}<ArrowRight size={16} /></button></form></div>;
}

export default function App() {
  const [blogs, setBlogs] = useState([]); const [auth, setAuth] = useState({ required: false, authenticated: true });
  const [publishing, setPublishing] = useState(null); const [selectedPlatforms, setSelectedPlatforms] = useState(null); const [connecting, setConnecting] = useState("");
  const [modelOptions, setModelOptions] = useState([]); const [ollamaOnline, setOllamaOnline] = useState(false);
  const [modelName, setModelName] = useState(() => window.localStorage.getItem("onkar-editorial-model") || "");
  const [apiOnline, setApiOnline] = useState(false); const [workflowId, setWorkflowId] = useState(""); const [workflow, setWorkflow] = useState(null);
  const [selected, setSelected] = useState(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(true); const [mobileSidebar, setMobileSidebar] = useState(false); const [events, setEvents] = useState([]); const [deleting, setDeleting] = useState("");
  const [topic, setTopic] = useState(""); const [length, setLength] = useState(LENGTHS[1]); const [submitting, setSubmitting] = useState(false); const [acting, setActing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [health, history, destinations, authState, modelInfo] = await Promise.all([api.health(), api.blogs(), api.publishing(), api.auth(), api.models()]);
      setApiOnline(health.status === "ok"); setBlogs(history); setPublishing(destinations); setAuth(authState);
      setModelOptions(modelInfo.models || []); setOllamaOnline(Boolean(modelInfo.ollama_online));
      setModelName((current) => modelInfo.models?.some((item) => item.id === current) ? current : modelInfo.default || "qwen3.5:4b");
      setSelectedPlatforms((current) => current === null
        ? Object.entries(destinations.destinations || {}).filter(([id, item]) => ["wordpress", "devto"].includes(id) && item.connected).map(([id]) => id)
        : current.filter((id) => destinations.destinations?.[id]?.connected));
      setError("");
    } catch (problem) { setApiOnline(false); setError(problem.message || "The backend is not available."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (modelName) window.localStorage.setItem("onkar-editorial-model", modelName); }, [modelName]);
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 7000); return () => window.clearInterval(timer); }, [refresh]);
  useEffect(() => {
    if (!workflowId) return undefined;
    let mounted = true;
    const poll = async () => { try { const state = await api.workflow(workflowId); if (mounted) { setWorkflow(state); setError(""); } } catch (problem) { if (mounted) setError(problem.message); } };
    poll(); const timer = window.setInterval(() => { if (!workflow || !["completed", "failed"].includes(workflow.status)) poll(); }, 1800);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [workflowId, workflow?.status]);

  async function generate(event) {
    event.preventDefault(); if (topic.trim().length < 3 || submitting) return;
    setSubmitting(true); setError(""); setSelected(null); setWorkflowId(""); setWorkflow(null); setEvents([]);
    const prompt = topic.trim();
    try { const selectedModel = modelName || "qwen3.5:4b"; const result = await api.createWorkflow({ topic: prompt, length, model_name: selectedModel }); setWorkflowId(result.workflow_id); setEvents([{ id: `prompt-${Date.now()}`, role: "user", text: prompt, model_name: selectedModel }]); setTopic(""); await refresh(); }
    catch (problem) { setError(problem.message); }
    finally { setSubmitting(false); }
  }
  async function openBlog(blog) {
    setWorkflowId(""); setWorkflow(null); setEvents([]); setMobileSidebar(false); setSelected({ ...blog, loading: true });
    try { const detail = await api.blog(blog.thread_id); setSelected({ ...blog, ...detail }); }
    catch { setSelected(blog); }
  }
  function newBlog() { setWorkflowId(""); setWorkflow(null); setEvents([]); setSelected(null); setTopic(""); setError(""); setMobileSidebar(false); }
  async function removeBlog(event, blog) {
    event.stopPropagation(); setDeleting(blog.thread_id); setError("");
    try { await api.deleteBlog(blog.thread_id); setBlogs((old) => old.filter((item) => item.thread_id !== blog.thread_id)); if (selected?.thread_id === blog.thread_id) setSelected(null); }
    catch (problem) { setError(problem.message); }
    finally { setDeleting(""); }
  }
  async function decide(action) {
    setActing(true); setError("");
    try { await api.action(workflowId, { action, platforms: action === "approve" && isApproval ? (selectedPlatforms || []) : [] }); setWorkflow((current) => ({ ...current, status: "running", pending: null })); }
    catch (problem) { setError(problem.message); if (problem.message.includes("Sign in")) setAuth((old) => ({ ...old, authenticated: false })); }
    finally { setActing(false); }
  }
  async function connect(platform) {
    if (!auth.authenticated) { setAuth((old) => ({ ...old, authenticated: false })); return; }
    setConnecting(platform); setError("");
    try { const result = await api.connect(platform); window.location.assign(`${base}${result.url}`); }
    catch (problem) { setError(problem.message); }
    finally { setConnecting(""); }
  }

  const running = Boolean(workflowId && workflow && !["completed", "failed"].includes(workflow.status));
  const article = selected || workflow?.pending?.blog || (workflow?.final ? { title: workflow.topic, content: workflow.final } : null);
  const review = workflow?.pending?.review || workflow?.review;
  const quality = workflow?.pending?.quality_gate || workflow?.quality_report;
  const isApproval = workflow?.pending?.type === "blog_review";
  const isLinkedIn = workflow?.pending?.type === "linkedin_approval";
  const destinations = publishing?.destinations || {};
  const canPublish = (selectedPlatforms || []).length > 0 && (selectedPlatforms || []).every((platform) => destinations[platform]?.connected);
  const canPublishLinkedIn = Boolean(destinations.linkedin?.connected);
  const chosenModel = modelOptions.find((item) => item.id === modelName);
  // The model list can report a tag variant differently from the requested
  // alias. Only block submission when the Ollama service itself is offline.
  const modelReady = ollamaOnline;
  const modelHint = !ollamaOnline ? "Start Ollama to generate with a local model."
    : chosenModel?.installed === false ? `Ollama is online, but did not match the “${modelName}” tag exactly. Sending is enabled; check OLLAMA_BASE_URL if generation fails.`
      : "Local model used for planning, thinking, writing, and review.";
  useEffect(() => {
    if (!workflowId || !workflow) return;
    const observed = workflow.events?.length ? workflow.events : workflow.node ? [{ node: workflow.node, stage: workflow.stage || workflow.node.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) }] : [];
    if (observed.length) setEvents((old) => {
      const known = new Set(old.map((item) => item.id));
      return [...old, ...observed.map((item, index) => ({ ...item, id: `${workflowId}-node-${index}-${item.node}`, role: "assistant", type: "node", text: item.stage || item.node }))
        .filter((item) => !known.has(item.id))];
    });
    if (workflow.pending && !events.some((item) => item.type === "approval")) setEvents((old) => [...old, { id: `${workflowId}-approval`, role: "assistant", type: "approval", text: "Draft ready for your review" }]);
    if (workflow.status === "completed" && !events.some((item) => item.type === "complete")) setEvents((old) => [...old, { id: `${workflowId}-complete`, role: "assistant", type: "complete", text: "Workflow complete" }]);
    if (workflow.status === "failed" && !events.some((item) => item.type === "failed")) setEvents((old) => [...old, { id: `${workflowId}-failed`, role: "assistant", type: "failed", text: workflow.error || "Workflow failed" }]);
  }, [workflowId, workflow]);

  return <div className="studio">
    {mobileSidebar && <button aria-label="Close history" className="sidebar-scrim" onClick={() => setMobileSidebar(false)} />}
    <aside className={cx("sidebar", mobileSidebar && "sidebar-open")}>
      <div className="side-brand"><span className="brand-mark"><Sparkles size={18} /></span><span><b>ONKAR AI</b><small>EDITORIAL STUDIO</small></span></div>
      <button className="new-chat" onClick={newBlog}><Plus size={16} />New blog</button>
      <div className="side-label">YOUR HISTORY <span>{blogs.length}</span></div>
      <div className="sidebar-history">{loading ? <div className="side-empty">Loading blogs…</div> : blogs.length ? blogs.map((blog) => <div key={blog.thread_id} className={cx("side-history-item", selected?.thread_id === blog.thread_id && "side-selected")}>
        <button className="history-select" onClick={() => openBlog(blog)} title={titleOf(blog)}><BookOpen size={14} /><span>{titleOf(blog)}</span></button>
        <button className="delete-blog" aria-label={`Delete ${titleOf(blog)}`} title="Delete blog" disabled={deleting === blog.thread_id} onClick={(event) => removeBlog(event, blog)}>{deleting === blog.thread_id ? <LoaderCircle size={14} className="spin" /> : <Trash2 size={14} />}</button>
      </div>) : <div className="side-empty">Your saved blogs will appear here.</div>}</div>
      <div className="sidebar-bottom"><span className={apiOnline ? "online-dot" : "offline-dot"} />{apiOnline ? "Agent online" : "Backend offline"}</div>
    </aside>
    <main className="chat-main">
      <header className="topbar"><button className="mobile-toggle" aria-label="Open history" onClick={() => setMobileSidebar(true)}><Menu size={18} /></button><div className="topbar-brand"><span>ONKAR AI</span><span className="top-divider">/</span><b>{selected ? titleOf(selected) : "New blog"}</b></div><div className="online"><i className={apiOnline ? "online-dot" : "offline-dot"} />{apiOnline ? "Agent online" : "Connecting"}</div></header>
      {error && <div className="alert"><CircleHelp size={16} />{error}<button onClick={() => { setError(""); refresh(); }} aria-label="Dismiss"><X size={15} /></button></div>}
      <div className="chat-scroll">
        <div className="chat-content">
          {!selected && !workflowId && !events.length && <div className="welcome"><span className="welcome-symbol"><Sparkles size={20} /></span><div className="kicker">YOUR WRITING ASSISTANT</div><h1>What story should we work on?</h1><p>Bring a question, idea, or point of view. I’ll understand it, research what matters, write a draft, and check it with you.</p></div>}
          {events.map((event) => event.role === "user" ? <div className="user-message" key={event.id}><div>{event.text}{event.model_name && <small>Using {modelLabel(event.model_name, modelOptions)} for thinking and writing</small>}</div></div> : <div className="agent-message" key={event.id}><span className={cx("agent-avatar", event.type)}>{event.type === "node" ? <Check size={14} /> : event.type === "failed" ? <CircleHelp size={14} /> : <Sparkles size={14} />}</span><div><div className="agent-name">{event.type === "node" ? "ONKAR · workflow" : "ONKAR AI"}</div><div className={cx("agent-copy", event.type)}>{event.type === "node" ? <><b>{pretty(event.text)}</b><small>Node executed</small></> : event.text}</div></div></div>)}
          {running && <div className="agent-message"><span className="agent-avatar thinking"><LoaderCircle size={14} /></span><div><div className="agent-name">ONKAR AI</div><div className="thinking-copy"><i /><i /><i /> Working on your article</div></div></div>}
          {article && (article.content || isLinkedIn) && <div className="agent-message article-message"><span className="agent-avatar"><Sparkles size={14} /></span><div className="article-message-inner"><div className="agent-name">{selected ? "SAVED BLOG" : "DRAFT FOR REVIEW"}</div><h2>{titleOf(article)}</h2><div className="article-body"><Suspense fallback={<p>Loading article…</p>}><MarkdownRenderer>{article.content || workflow?.final || ""}</MarkdownRenderer></Suspense></div>
            {workflow?.pending?.type === "linkedin_approval" && <div className="publication-results"><h3>Article published</h3><p>Review the published links before approving the LinkedIn post.</p><PublicationResults links={workflow.pending.platform_links || workflow.published_links} primaryUrl={workflow.pending.primary_url} /></div>}
            {isLinkedIn && workflow.pending.draft?.text && <div className="linkedin-draft"><h3>LinkedIn post preview</h3><p>{workflow.pending.draft.text}</p></div>}
            {workflow?.status === "completed" && <div className="publication-results"><h3>Publishing results</h3><PublicationResults links={workflow.final_result?.platforms || workflow.published_links} primaryUrl={workflow.final_result?.successful_urls?.[0]} linkedin={workflow.final_result?.linkedin} /></div>}
            {(quality || review) && <div className="review-data">{quality && <Report title="Quality checks" report={quality} />}{review && <Report title="Editorial review" report={review} />}</div>}
            {isApproval && <div className="approval-box approval-stack"><div><b>Your draft is ready</b><span>{quality?.status === "failed" ? "The automated quality check flagged this draft. Review its findings before deciding." : "Choose where to publish. The article will publish after your approval."}</span></div><div className="publish-choices">{["wordpress", "devto"].map((platform) => { const destination = destinations[platform] || {}; const name = destination.name || (platform === "wordpress" ? "WordPress.com" : "DEV.to"); return <div className="publish-choice" key={platform}><label className={!destination.connected ? "choice-disabled" : ""}><input type="checkbox" checked={(selectedPlatforms || []).includes(platform)} disabled={!destination.connected || acting} onChange={() => setSelectedPlatforms((old) => (old || []).includes(platform) ? old.filter((item) => item !== platform) : [...(old || []), platform])} /><span><b>{name}</b><small>{destination.connected ? "Connected · ready to publish" : destination.configured ? "Connection required" : "Not configured"}</small></span></label>{!destination.connected && destination.configured && destination.connect_url && <button className="connect-button" disabled={connecting === platform || !auth.authenticated} onClick={() => connect(platform)}>{connecting === platform ? <LoaderCircle size={12} className="spin" /> : "Connect"}</button>}</div>; })}</div><div className="approval-actions"><button className="secondary-button" disabled={acting} onClick={() => decide("reject")}>Reject draft</button><button className="primary-button" disabled={acting || !auth.authenticated || !canPublish} onClick={() => decide("approve")}><Check size={15} />Approve & publish</button></div>{!canPublish && <small className="publish-hint">Connect and select at least one publishing platform to continue.</small>}</div>}
            {isLinkedIn && <div className="approval-box"><div><b>LinkedIn post needs approval</b><span>Review the post and published article link above before sharing.</span></div><div className="approval-actions"><button className="secondary-button" disabled={acting} onClick={() => decide("reject")}>Reject</button><button className="primary-button" disabled={acting || !auth.authenticated || !canPublishLinkedIn} onClick={() => decide("approve")}><Send size={15} />Approve & post to LinkedIn</button></div>{!canPublishLinkedIn && <div className="connect-linkedin"><span>{destinations.linkedin?.configured ? "LinkedIn is not connected." : "LinkedIn OAuth is not configured."}</span>{destinations.linkedin?.configured && <button className="connect-button" disabled={connecting === "linkedin" || !auth.authenticated} onClick={() => connect("linkedin")}>{connecting === "linkedin" ? <LoaderCircle size={12} className="spin" /> : "Connect LinkedIn"}</button>}</div>}</div>}
            {workflow?.status === "failed" && <div className="inline-message error-text">{workflow.error || "Workflow stopped."}</div>}
            {workflow?.status === "completed" && <div className="success-note"><Check size={15} />Workflow finished{workflow.final_result?.successful_urls?.length ? ` · ${workflow.final_result.successful_urls.length} publication(s)` : ""}</div>}
          </div></div>}
          {workflow?.status === "failed" && !article && <div className="agent-message"><span className="agent-avatar failed"><CircleHelp size={14} /></span><div><div className="agent-name">ONKAR AI</div><div className="agent-copy failed">{workflow.error || "Workflow stopped. Please try again."}</div></div></div>}
        </div>
      </div>
      {!selected && <div className="composer-wrap"><form className="composer" onSubmit={generate}><label className="composer-topic-label" htmlFor="topic">Your idea</label><textarea id="topic" value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="Describe the blog you want to create…" minLength={3} maxLength={2000} required /><div className="composer-controls"><div className="composer-options"><label title="Choose the article depth"><span>Length</span><select value={length} onChange={(event) => setLength(event.target.value)}>{LENGTHS.map((item) => <option key={item}>{item}</option>)}</select></label><label title="Used for planning, thinking, drafting, and review"><span>Model</span><select className="model-select" value={modelName || "qwen3.5:4b"} onChange={(event) => setModelName(event.target.value)} aria-label="Choose AI model">{(modelOptions.length ? modelOptions : [{ id: "qwen3.5:4b", label: "Qwen 3.5 · 4B" }, { id: "gemma3:4b", label: "Gemma 3 · 4B" }]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label></div><button className="send-button" aria-label="Generate blog" disabled={submitting || topic.trim().length < 3 || !modelReady}>{submitting ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}</button></div><div className="composer-hint"><LockKeyhole size={12} />{modelHint}</div></form></div>}
      <footer className="chat-footer"><span>ONKAR AI can make mistakes. Review important details.</span></footer>
    </main>
    {auth.required && !auth.authenticated && <SignIn onLogin={async (password) => { await api.login(password); setAuth((old) => ({ ...old, authenticated: true })); }} />}
  </div>;
}

function Report({ title, report }) {
  const entries = Object.entries(report || {}).filter(([key, value]) => key !== "findings" && value !== null && value !== undefined && value !== "");
  const findings = Array.isArray(report?.findings) ? report.findings : [];
  const valueOf = (value) => typeof value === "boolean" ? (value ? "Yes" : "No") : Array.isArray(value) ? value.join(" · ") : typeof value === "object" ? Object.entries(value || {}).map(([key, item]) => `${pretty(key)}: ${String(item)}`).join(" · ") : String(value);
  return <div className="report"><h3>{title}</h3>{entries.length ? entries.map(([key, value]) => <div className="report-row" key={key}><span>{pretty(key)}</span><b>{valueOf(value)}</b></div>) : null}{findings.map((finding, index) => <div className="finding" key={`${finding.category}-${index}`}><div><span className={`severity severity-${finding.severity || "minor"}`}>{pretty(finding.severity || "finding")}</span><span className="finding-category">{pretty(finding.category)}</span></div>{finding.excerpt && <b className="finding-excerpt">{finding.excerpt}</b>}{finding.issue && <p>{finding.issue}</p>}{finding.correction && <small>Suggested fix: {finding.correction}</small>}</div>)}{!entries.length && !findings.length && <p>No details returned.</p>}</div>;
}

function PublicationResults({ links, primaryUrl, linkedin }) {
  const entries = Object.entries(links || {}).filter(([platform]) => ["wordpress", "devto"].includes(platform));
  if (linkedin) entries.push(["linkedin", linkedin]);
  return <div className="publication-list">{primaryUrl && <div className="primary-link"><span>Article link</span><a href={primaryUrl} target="_blank" rel="noreferrer">{primaryUrl} <ArrowRight size={12} /></a></div>}{entries.length ? entries.map(([platform, result]) => <div className="publication-line" key={platform}><span>{platform === "wordpress" ? "WordPress" : platform === "devto" ? "DEV.to" : "LinkedIn"}</span><b className={result?.status === "published" ? "result-good" : "result-muted"}>{pretty(result?.status || "not published")}</b>{result?.url && <a href={result.url} target="_blank" rel="noreferrer">Open post <ArrowRight size={12} /></a>}{result?.error && <small>{result.error}</small>}</div>) : <p>No publishing results available yet.</p>}</div>;
}
