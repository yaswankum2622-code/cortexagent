"""CortexAgent - Streamlit Dashboard with premium product styling."""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

import httpx
import streamlit as st


API_BASE = os.environ.get("CORTEX_API_BASE", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="CortexAgent - SEC Research",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css() -> None:
    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as file:
            st.markdown(f"<style>{file.read()}</style>", unsafe_allow_html=True)


load_css()


if "history" not in st.session_state:
    st.session_state.history = []

if "last_response" not in st.session_state:
    st.session_state.last_response = None

if "is_running" not in st.session_state:
    st.session_state.is_running = False

if "audit_cache" not in st.session_state:
    st.session_state.audit_cache = {}

if "query_input" not in st.session_state:
    st.session_state.query_input = ""

if "example_select" not in st.session_state:
    st.session_state.example_select = "Choose an example query"

if "last_example_select" not in st.session_state:
    st.session_state.last_example_select = st.session_state.example_select


@st.cache_data(ttl=10)
def fetch_health() -> Dict[str, Any]:
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"status": "unreachable", "error": str(exc)}


@st.cache_data(ttl=2)
def fetch_cost() -> Dict[str, Any]:
    try:
        response = httpx.get(f"{API_BASE}/cost", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"queries_served": 0, "estimated_usd": 0.0, "by_model": {}}


def fetch_audit(thread_id: str) -> Dict[str, Any]:
    try:
        response = httpx.get(f"{API_BASE}/audit/{thread_id}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {
            "thread_id": thread_id,
            "entries": [],
            "total_entries": 0,
            "error": str(exc),
        }


def submit_research(query: str) -> Dict[str, Any]:
    response = httpx.post(
        f"{API_BASE}/research",
        json={"query": query},
        timeout=600.0,
    )
    response.raise_for_status()
    return response.json()


def render_metric_card(label: str, value: str, accent: bool = False) -> str:
    accent_class = " cortex-metric-accent" if accent else ""
    return f"""
    <div class="cortex-card">
        <div class="cortex-metric-label">{label}</div>
        <div class="cortex-metric-value{accent_class}">{value}</div>
    </div>
    """


def render_status_row(label: str, ok: bool, value: str) -> str:
    dot_class = "live" if ok else "offline"
    return f"""
    <div class="status-row">
        <div class="status-label"><span class="status-dot {dot_class}"></span>{label}</div>
        <div class="status-value">{value}</div>
    </div>
    """


def render_history_item(item: Dict[str, Any]) -> str:
    thread_tail = item["thread_id"][-8:]
    return f"""
    <div class="history-item">
        <div class="history-item-title">{item['query'][:70]}</div>
        <div class="history-item-meta">thread {thread_tail} / +${item.get('cost_delta', 0):.4f}</div>
    </div>
    """


def render_model_row(model: str, usd: float, tokens: int) -> str:
    return f"""
    <div class="model-row">
        <div class="history-item-title"><code>{model}</code></div>
        <div class="history-item-meta">${usd:.4f} / {tokens:,} tokens</div>
    </div>
    """


def render_model_strip(models: list[str]) -> None:
    if not models:
        return

    html = '<div class="model-strip">'
    for model in models:
        html += f'<div class="model-pill">{model}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_agent_flow(active: str | None = None, complete: list[str] | None = None) -> None:
    complete = complete or []
    agents = [
        ("researcher", "R", "Research"),
        ("analyst", "A", "Analysis"),
        ("writer", "W", "Writing"),
        ("critic", "C", "Critique"),
    ]

    html = '<div class="agent-flow">'
    for key, badge, name in agents:
        css_class = "agent-node"
        if key == active:
            css_class += " active"
        elif key in complete:
            css_class += " complete"
        html += (
            f'<div class="{css_class}">'
            f'<div class="agent-icon">{badge}</div>'
            f'<div class="agent-name">{name}</div>'
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_citation_card(citation: Dict[str, Any]) -> str:
    preview = citation.get("preview", "")[:300]
    return f"""
    <div class="citation-card">
        <div class="citation-meta">{citation.get("ticker", "?")} / {citation.get("year", "?")} / {citation.get("chunk_id", "?")}</div>
        <div class="citation-preview">{preview}...</div>
    </div>
    """


def render_hero(health: Dict[str, Any], cost: Dict[str, Any]) -> None:
    provider_count = sum(1 for enabled in health.get("providers_configured", {}).values() if enabled)
    chunk_count = f"{health.get('chroma_chunks', 0):,}"
    query_count = cost.get("queries_served", 0)
    est_cost = f"${cost.get('estimated_usd', 0.0):.4f}"
    html = f"""
    <div class="cortex-hero">
        <div class="hero-grid">
            <div class="hero-copy">
                <div class="hero-eyebrow">Production AI Research Stack</div>
                <div class="cortex-hero-title">CortexAgent</div>
                <div class="cortex-hero-subtitle">
                    A multi-agent financial research system that behaves like a product, not a notebook.
                    It fuses hybrid retrieval, iterative critique, safety testing, and cost observability into
                    one recruiter-facing experience.
                </div>
                <div class="hero-meta">
                    <span class="cortex-pill">3-provider cascade</span>
                    <span class="cortex-pill">Hybrid retrieval + reranker</span>
                    <span class="cortex-pill">RAGAS-gated CI</span>
                    <span class="cortex-pill">Adversarially tested</span>
                    <span class="cortex-pill">LAN demo ready</span>
                </div>
            </div>
            <div class="hero-stage">
                <div class="hero-stage-shell">
                    <div class="hero-orb orb-cyan"></div>
                    <div class="hero-orb orb-violet"></div>
                    <div class="hero-panel">
                        <div class="hero-panel-label">Live index</div>
                        <div class="hero-panel-value">{chunk_count} chunks</div>
                        <div class="hero-panel-meta">
                            Chroma-backed 2024 filings for Apple, Microsoft, Alphabet, JPMorgan, and Tesla.
                            API status: <strong>{health.get("status", "unknown")}</strong>
                        </div>
                    </div>
                    <div class="hero-kpi-grid">
                        <div class="hero-kpi-card">
                            <div class="hero-kpi-label">Providers</div>
                            <div class="hero-kpi-value">{provider_count} / 3</div>
                            <div class="hero-kpi-subtext">Anthropic, Gemini, Groq</div>
                        </div>
                        <div class="hero-kpi-card">
                            <div class="hero-kpi-label">Session spend</div>
                            <div class="hero-kpi-value">{est_cost}</div>
                            <div class="hero-kpi-subtext">Live API-side cost tracker</div>
                        </div>
                        <div class="hero-kpi-card">
                            <div class="hero-kpi-label">Queries served</div>
                            <div class="hero-kpi-value">{query_count}</div>
                            <div class="hero-kpi-subtext">Current FastAPI process</div>
                        </div>
                        <div class="hero-kpi-card">
                            <div class="hero-kpi-label">Mode</div>
                            <div class="hero-kpi-value">Agentic</div>
                            <div class="hero-kpi-subtext">Research / write / critique loop</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar(health: Dict[str, Any], cost: Dict[str, Any]) -> None:
    with st.sidebar:
        st.title("CortexAgent")
        st.caption("SEC research product surface powered by the FastAPI backend")

        st.divider()
        st.subheader("System")
        if health.get("status") == "ok":
            st.success("API healthy")
        elif health.get("status") == "degraded":
            st.warning("API degraded")
        else:
            st.error("API unreachable")

        st.markdown(
            render_metric_card(
                "Indexed Chunks",
                f"{health.get('chroma_chunks', 0):,}",
                accent=True,
            ),
            unsafe_allow_html=True,
        )

        providers = health.get("providers_configured", {})
        st.markdown(
            render_status_row("Anthropic", bool(providers.get("anthropic")), "online" if providers.get("anthropic") else "offline"),
            unsafe_allow_html=True,
        )
        st.markdown(
            render_status_row("Gemini", bool(providers.get("gemini")), "online" if providers.get("gemini") else "offline"),
            unsafe_allow_html=True,
        )
        st.markdown(
            render_status_row("Groq", bool(providers.get("groq")), "online" if providers.get("groq") else "offline"),
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("Cost")
        st.markdown(
            render_metric_card("Estimated USD", f"${cost.get('estimated_usd', 0.0):.4f}", accent=True),
            unsafe_allow_html=True,
        )
        st.markdown(
            render_metric_card("Queries Served", str(cost.get("queries_served", 0))),
            unsafe_allow_html=True,
        )

        for model, stats in cost.get("by_model", {}).items():
            total_tokens = stats.get("input_tokens", 0) + stats.get("output_tokens", 0)
            st.markdown(
                render_model_row(model, float(stats.get("usd", 0.0)), total_tokens),
                unsafe_allow_html=True,
            )

        st.divider()
        st.subheader("Recent queries")
        if st.session_state.history:
            for item in reversed(st.session_state.history[-4:]):
                st.markdown(render_history_item(item), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="sidebar-note">No completed runs yet. Submit a research question to populate live history.</div>',
                unsafe_allow_html=True,
            )


def render_query_section() -> tuple[str, bool]:
    st.markdown(
        """
        <div class="control-shell">
            <div class="section-kicker">Research console</div>
            <div class="section-title">Ask the orchestrator a filing question</div>
            <div class="section-copy">
                The dashboard is only a client. All reasoning, retrieval, citations, audit logging, and cost tracking
                come from the FastAPI backend.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_input, col_examples, col_button = st.columns([5, 3, 2])

    with col_examples:
        example = st.selectbox(
            "Examples",
            [
                "Choose an example query",
                "What are Apple's main business segments in fiscal 2024?",
                "How large was Microsoft's Cloud business in fiscal 2024?",
                "What risks does Tesla disclose around Autopilot?",
                "What are JPMorgan's four main business segments?",
                "How is Alphabet positioning AI in 2024?",
            ],
            label_visibility="collapsed",
            key="example_select",
        )

    if (
        example != "Choose an example query"
        and example != st.session_state.get("last_example_select")
    ):
        st.session_state.query_input = example
    st.session_state.last_example_select = example

    with col_input:
        query = st.text_input(
            "Research Query",
            placeholder="What are Apple's main business segments in fiscal 2024?",
            label_visibility="collapsed",
            key="query_input",
        )

    with col_button:
        submit = st.button(
            "Run Research",
            type="primary",
            use_container_width=True,
            disabled=not query,
        )

    return query, submit


def run_query(query: str) -> None:
    st.session_state.is_running = True

    flow_placeholder = st.empty()
    with flow_placeholder.container():
        render_agent_flow(active="researcher")

    status_placeholder = st.empty()
    status_placeholder.info(
        "Running multi-agent orchestration. Live node logs are visible in the FastAPI server window."
    )

    fetch_cost.clear()
    cost_before = fetch_cost().get("estimated_usd", 0.0)

    try:
        started = time.time()
        result = submit_research(query)
        elapsed = time.time() - started

        flow_placeholder.empty()
        with flow_placeholder.container():
            render_agent_flow(complete=["researcher", "analyst", "writer", "critic"])

        status_placeholder.success(
            f"Completed in {elapsed:.1f}s with {result.get('revision_count', 0)} revision(s)."
        )

        st.session_state.last_response = result
        fetch_cost.clear()
        cost_after = fetch_cost().get("estimated_usd", 0.0)
        st.session_state.history.append(
            {
                "query": query,
                "thread_id": result["thread_id"],
                "cost_delta": max(cost_after - cost_before, 0.0),
            }
        )
    except httpx.TimeoutException:
        status_placeholder.error("Request timed out after 10 minutes. Check API logs.")
    except httpx.HTTPStatusError as exc:
        status_placeholder.error(
            f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        )
    except Exception as exc:
        status_placeholder.error(f"Request failed: {exc}")
    finally:
        st.session_state.is_running = False


def render_report_tab(result: Dict[str, Any]) -> None:
    st.markdown(result.get("report", "*No report returned.*"))


def render_citations_tab(result: Dict[str, Any]) -> None:
    citations = result.get("citations", [])
    if not citations:
        st.info("No citations returned.")
        return

    for citation in citations:
        st.markdown(render_citation_card(citation), unsafe_allow_html=True)


def render_critic_tab(result: Dict[str, Any]) -> None:
    critique = result.get("critique")
    if not critique:
        st.info("No critic output returned.")
        return

    decision = critique.get("decision", "unknown")
    st.markdown(f"### Decision: `{decision}`")

    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.markdown(
            render_metric_card("Faithfulness", f"{critique.get('faithfulness', 0)}/5", accent=True),
            unsafe_allow_html=True,
        )
    with metric_cols[1]:
        st.markdown(
            render_metric_card("Completeness", f"{critique.get('completeness', 0)}/5", accent=True),
            unsafe_allow_html=True,
        )
    with metric_cols[2]:
        st.markdown(
            render_metric_card("Citation Quality", f"{critique.get('citation_quality', 0)}/5", accent=True),
            unsafe_allow_html=True,
        )

    if critique.get("feedback"):
        st.info(critique["feedback"])

    if result.get("retrieval_grade"):
        st.markdown("**Retrieval grade payload**")
        st.code(json.dumps(result["retrieval_grade"], indent=2), language="json")


def render_audit_tab(thread_id: str) -> None:
    load_clicked = st.button("Load full audit trail", use_container_width=False)
    if load_clicked or thread_id in st.session_state.audit_cache:
        if load_clicked:
            st.session_state.audit_cache[thread_id] = fetch_audit(thread_id)

        audit = st.session_state.audit_cache.get(thread_id, {})
        if audit.get("error"):
            st.error(f"Audit fetch failed: {audit['error']}")
            return

        st.markdown(f"**Total entries:** {audit.get('total_entries', 0)}")
        for entry in audit.get("entries", []):
            title = (
                f"{entry.get('agent', '?')}.{entry.get('action', '?')} / "
                f"{entry.get('latency_ms', 0)}ms"
            )
            with st.expander(title):
                st.caption(f"Timestamp: {entry.get('timestamp', '?')}")
                if entry.get("model"):
                    st.caption(f"Model: {entry['model']}")
                if entry.get("input_summary"):
                    st.caption(f"Input: {entry['input_summary'][:280]}")
                if entry.get("output_summary"):
                    st.caption(f"Output: {entry['output_summary'][:280]}")


def render_results() -> None:
    result = st.session_state.last_response
    if not result:
        st.markdown(
            """
            <div class="empty-shell">
                <div class="empty-title">Ready for a real demo run</div>
                <div class="empty-copy">
                    Use one of the example prompts above or ask your own question about Apple, Microsoft,
                    Alphabet, JPMorgan, or Tesla. The result will appear here with citations, audit trail,
                    critic scores, and cost metadata.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="results-shell"></div>', unsafe_allow_html=True)
    render_agent_flow(complete=["researcher", "analyst", "writer", "critic"])

    top_metrics = st.columns(4)
    with top_metrics[0]:
        st.markdown(
            render_metric_card("Thread", result["thread_id"][-8:], accent=True),
            unsafe_allow_html=True,
        )
    with top_metrics[1]:
        st.markdown(
            render_metric_card("Revisions", str(result.get("revision_count", 0))),
            unsafe_allow_html=True,
        )
    with top_metrics[2]:
        st.markdown(
            render_metric_card("Latency", f"{result.get('wall_latency_ms', 0) / 1000:.1f}s"),
            unsafe_allow_html=True,
        )
    with top_metrics[3]:
        st.markdown(
            render_metric_card("Citations", str(len(result.get("citations", [])))),
            unsafe_allow_html=True,
        )

    render_model_strip(result.get("models_used", []))

    tab_report, tab_citations, tab_critic, tab_audit = st.tabs(
        ["Report", "Citations", "Critic Review", "Audit Trail"]
    )

    with tab_report:
        render_report_tab(result)

    with tab_citations:
        render_citations_tab(result)

    with tab_critic:
        render_critic_tab(result)

    with tab_audit:
        render_audit_tab(result["thread_id"])


health = fetch_health()
cost = fetch_cost()

render_sidebar(health, cost)
render_hero(health, cost)

query, submit = render_query_section()
if submit and query:
    run_query(query)

render_results()
