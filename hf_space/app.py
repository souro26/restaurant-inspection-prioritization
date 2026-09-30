from html import escape
from pathlib import Path

import gradio as gr
import pandas as pd
import spaces


@spaces.GPU
def _zerogpu_compatibility_hook():
    """Minimal ZeroGPU hook; the application itself remains CPU-only."""
    return None


# ============================================================
# Configuration
# ============================================================

APP_DIR = Path(__file__).resolve().parent

SCORES_PATH = APP_DIR / "restaurant_risk_scores.csv"
QUEUE_PATH = APP_DIR / "restaurant_priority_queue.csv"

MAX_CAPACITY = 500
MAX_SEARCH_LENGTH = 100
MAX_SEARCH_RESULTS = 25


# ============================================================
# Data loading
# ============================================================

def load_data():
    if not SCORES_PATH.is_file():
        raise FileNotFoundError(
            f"Required scoring file not found: {SCORES_PATH}"
        )

    if not QUEUE_PATH.is_file():
        raise FileNotFoundError(
            f"Required priority queue file not found: {QUEUE_PATH}"
        )

    scores = pd.read_csv(SCORES_PATH)
    queue = pd.read_csv(QUEUE_PATH)

    required_columns = {
        "camis",
        "restaurant_name",
        "borough",
        "cuisine_description",
        "cutoff_date",
        "history_depth_bucket",
        "raw_logistic_probability",
        "calibrated_high_severity_probability",
        "priority_rank",
    }

    missing = required_columns - set(scores.columns)

    if missing:
        raise ValueError(
            "The scoring file is missing required columns: "
            + ", ".join(sorted(missing))
        )

    scores["priority_rank"] = pd.to_numeric(
        scores["priority_rank"],
        errors="coerce",
    )

    scores["calibrated_high_severity_probability"] = pd.to_numeric(
        scores["calibrated_high_severity_probability"],
        errors="coerce",
    )

    scores["raw_logistic_probability"] = pd.to_numeric(
        scores["raw_logistic_probability"],
        errors="coerce",
    )

    scores = scores.dropna(
        subset=[
            "priority_rank",
            "calibrated_high_severity_probability",
        ]
    ).copy()

    scores["priority_rank"] = (
        scores["priority_rank"].astype(int)
    )

    scores = scores.sort_values(
        "priority_rank",
        ascending=True,
    ).reset_index(drop=True)

    return scores, queue


SCORES, ORIGINAL_QUEUE = load_data()

TOTAL_RESTAURANTS = len(SCORES)

BOROUGHS = sorted(
    SCORES["borough"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

CUISINES = sorted(
    SCORES["cuisine_description"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


# ============================================================
# Formatting
# ============================================================

def format_probability(value):
    if pd.isna(value):
        return "—"

    return f"{float(value) * 100:.1f}%"


def safe_text(value):
    if pd.isna(value):
        return "—"

    return escape(str(value))


def risk_class(probability):
    """
    Used only for visual presentation.
    The underlying probability remains the actual model output.
    """

    try:
        value = float(probability)

        if value >= 0.70:
            return "risk-high"

        if value >= 0.40:
            return "risk-medium"

        return "risk-low"

    except (TypeError, ValueError):
        return "risk-low"


# ============================================================
# Validation
# ============================================================

def parse_capacity(value):
    """
    Parse the capacity field.

    Empty input is deliberately allowed while the user is editing.
    This prevents an error from appearing when they press Backspace
    before entering the next number.
    """

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    if not value.isdigit():
        raise gr.Error(
            "Inspection capacity must be a whole number."
        )

    capacity = int(value)

    if capacity < 1:
        raise gr.Error(
            "Inspection capacity must be at least 1."
        )

    if capacity > MAX_CAPACITY:
        raise gr.Error(
            f"Inspection capacity cannot exceed {MAX_CAPACITY}."
        )

    if capacity > TOTAL_RESTAURANTS:
        raise gr.Error(
            "Inspection capacity exceeds the available restaurant population."
        )

    return capacity


# ============================================================
# Filtering
# ============================================================

def filtered_population(
    selected_boroughs,
    selected_cuisines,
):
    df = SCORES

    selected_boroughs = selected_boroughs or []
    selected_cuisines = selected_cuisines or []

    if selected_boroughs:
        df = df[
            df["borough"].isin(selected_boroughs)
        ]

    if selected_cuisines:
        df = df[
            df["cuisine_description"].isin(
                selected_cuisines
            )
        ]

    return df


# ============================================================
# Queue rendering
# ============================================================

def render_queue(
    capacity,
    selected_boroughs=None,
    selected_cuisines=None,
):
    capacity = parse_capacity(capacity)

    # User is currently editing the field.
    # Keep the existing queue instead of generating an error.
    if capacity is None:
        return gr.skip()

    df = filtered_population(
        selected_boroughs,
        selected_cuisines,
    )

    if df.empty:
        raise gr.Error(
            "No restaurants match the selected filters."
        )

    queue = df.head(capacity)

    cards = []

    for _, row in queue.iterrows():

        rank = int(row["priority_rank"])

        restaurant = safe_text(
            row["restaurant_name"]
        )

        borough = safe_text(
            row["borough"]
        )

        cuisine = safe_text(
            row["cuisine_description"]
        )

        camis = safe_text(
            row["camis"]
        )

        probability = float(
            row["calibrated_high_severity_probability"]
        )

        risk = format_probability(probability)

        risk_type = risk_class(probability)

        # Width is purely visual.
        # It represents the probability on a 0–100 scale.
        bar_width = max(
            0,
            min(100, probability * 100),
        )

        cutoff_date = safe_text(row["cutoff_date"])
        history_depth = safe_text(row["history_depth_bucket"])
        raw_probability = format_probability(
            row["raw_logistic_probability"]
        )

        cards.append(
            f"""
            <details class="queue-card">

                <summary class="queue-summary">

                    <div class="queue-rank">
                        {rank}
                    </div>

                    <div class="queue-main">

                        <div class="queue-title-row">

                            <div class="queue-name">
                                {restaurant}
                            </div>

                            <div class="queue-risk {risk_type}">
                                {risk}
                            </div>

                        </div>

                        <div class="queue-meta">

                            <span>
                                {borough}
                            </span>

                            <span class="meta-separator">
                                ·
                            </span>

                            <span>
                                {cuisine}
                            </span>

                            <span class="meta-separator">
                                ·
                            </span>

                            <span>
                                CAMIS {camis}
                            </span>

                        </div>

                        <div class="risk-track">
                            <div
                                class="risk-fill {risk_type}"
                                style="width: {bar_width:.1f}%"
                            ></div>
                        </div>

                        <div class="queue-expand-hint">
                            Click for restaurant details
                        </div>

                    </div>

                    <span class="queue-chevron" aria-hidden="true">
                        ›
                    </span>

                </summary>

                <div class="queue-details">

                    <div class="detail-item">
                        <span class="detail-label">CAMIS</span>
                        <span class="detail-value">{camis}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">Borough</span>
                        <span class="detail-value">{borough}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">Cuisine</span>
                        <span class="detail-value">{cuisine}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">Priority rank</span>
                        <span class="detail-value">#{rank:,}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">Calibrated risk</span>
                        <span class="detail-value {risk_type}">{risk}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">Raw model probability</span>
                        <span class="detail-value">{raw_probability}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">Cutoff date</span>
                        <span class="detail-value">{cutoff_date}</span>
                    </div>

                    <div class="detail-item">
                        <span class="detail-label">History depth</span>
                        <span class="detail-value">{history_depth}</span>
                    </div>

                </div>

            </details>
            """
        )

    return f"""
    <div class="queue-shell">

        <div class="queue-header">

            <div>
                <div class="queue-heading">
                    Priority queue
                </div>

                <div class="queue-subheading">
                    Top {len(queue):,} restaurant
                    {"s" if len(queue) != 1 else ""}
                    under the current selection
                </div>
            </div>

            <div class="queue-count">
                {len(queue):,}
            </div>

        </div>

        <div class="queue-list">
            {''.join(cards)}
        </div>

    </div>
    """


# ============================================================
# Restaurant search
# ============================================================

def search_restaurants(query):
    query = str(query or "").strip()

    if not query:
        raise gr.Error(
            "Enter a restaurant name or CAMIS ID."
        )

    if len(query) > MAX_SEARCH_LENGTH:
        raise gr.Error(
            "Search query is too long."
        )

    query_lower = query.lower()

    restaurant_names = (
        SCORES["restaurant_name"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    camis_values = (
        SCORES["camis"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    mask = (
        restaurant_names.str.contains(
            query_lower,
            regex=False,
            na=False,
        )
        |
        camis_values.str.contains(
            query_lower,
            regex=False,
            na=False,
        )
    )

    results = SCORES.loc[mask].head(
        MAX_SEARCH_RESULTS
    )

    if results.empty:
        raise gr.Error(
            "No matching restaurant was found."
        )

    cards = []

    for _, row in results.iterrows():

        rank = int(row["priority_rank"])

        restaurant = safe_text(
            row["restaurant_name"]
        )

        borough = safe_text(
            row["borough"]
        )

        cuisine = safe_text(
            row["cuisine_description"]
        )

        camis = safe_text(
            row["camis"]
        )

        probability = float(
            row["calibrated_high_severity_probability"]
        )

        risk = format_probability(probability)

        risk_type = risk_class(probability)

        bar_width = max(
            0,
            min(100, probability * 100),
        )

        cards.append(
            f"""
            <article class="search-card">

                <div class="search-rank">
                    #{rank}
                </div>

                <div class="search-main">

                    <div class="search-title-row">

                        <div class="search-name">
                            {restaurant}
                        </div>

                        <div class="queue-risk {risk_type}">
                            {risk}
                        </div>

                    </div>

                    <div class="queue-meta">

                        <span>
                            {borough}
                        </span>

                        <span class="meta-separator">
                            ·
                        </span>

                        <span>
                            {cuisine}
                        </span>

                        <span class="meta-separator">
                            ·
                        </span>

                        <span>
                            CAMIS {camis}
                        </span>

                    </div>

                    <div class="risk-track">
                        <div
                            class="risk-fill {risk_type}"
                            style="width: {bar_width:.1f}%"
                        ></div>
                    </div>

                </div>

            </article>
            """
        )

    return f"""
    <div class="search-results">

        <div class="search-result-heading">
            {len(results):,} matching result
            {"s" if len(results) != 1 else ""}
        </div>

        {''.join(cards)}

    </div>
    """


# ============================================================
# Reset
# ============================================================

def reset_filters():
    return (
        "100",
        [],
        [],
        render_queue(
            "100",
            [],
            [],
        ),
    )


# ============================================================
# CSS
# ============================================================

CSS = r"""
/* ==========================================================
   Base
========================================================== */

.gradio-container {
    max-width: 1180px !important;
    margin: 0 auto !important;
    padding-bottom: 70px !important;
}

body {
    background:
        radial-gradient(
            circle at 12% 0%,
            rgba(99, 102, 241, 0.10),
            transparent 28%
        ),
        radial-gradient(
            circle at 90% 8%,
            rgba(14, 165, 233, 0.07),
            transparent 24%
        );
}


/* ==========================================================
   Hero
========================================================== */

.hero {
    position: relative;
    overflow: hidden;
    margin: 18px 0 38px 0;
    padding: 58px 52px;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 26px;
    background:
        linear-gradient(
            135deg,
            #111827 0%,
            #1e293b 58%,
            #172554 100%
        );
    color: white;
    box-shadow:
        0 24px 70px rgba(15, 23, 42, 0.22);
}

.hero::before {
    content: "";
    position: absolute;
    width: 360px;
    height: 360px;
    right: -120px;
    top: -190px;
    border-radius: 50%;
    background: rgba(99, 102, 241, 0.20);
    filter: blur(10px);
}

.hero::after {
    content: "";
    position: absolute;
    width: 240px;
    height: 240px;
    right: 160px;
    bottom: -190px;
    border-radius: 50%;
    background: rgba(14, 165, 233, 0.12);
}

.hero-content {
    position: relative;
    z-index: 2;
    max-width: 800px;
}

.hero-eyebrow {
    display: inline-block;
    margin-bottom: 18px;
    padding: 7px 13px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.07);
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 750;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.hero h1 {
    margin: 0 0 15px 0 !important;
    font-size: clamp(34px, 5vw, 58px) !important;
    line-height: 1.02 !important;
    letter-spacing: -0.045em !important;
}

.hero p {
    max-width: 720px;
    margin: 0 !important;
    color: #cbd5e1;
    font-size: 17px;
    line-height: 1.65;
}


/* ==========================================================
   Section headings
========================================================== */

.section-heading {
    margin: 28px 0 15px 0;
}

.section-heading h2 {
    margin: 0 0 6px 0 !important;
    letter-spacing: -0.025em;
}

.section-heading p {
    margin: 0 !important;
    color: #64748b;
}


/* ==========================================================
   Control panel
========================================================== */

.control-panel {
    position: relative !important;
    z-index: 100 !important;
    overflow: visible !important;
    padding: 20px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.72);
    box-shadow:
        0 12px 38px rgba(15, 23, 42, 0.06);
    backdrop-filter: blur(10px);
}

.dark .control-panel {
    background: rgba(15, 23, 42, 0.66);
}


/* ==========================================================
   Dropdown stacking
   Let Gradio control the dropdown menu positioning.
   We only make sure the control panel can overflow above the
   sections that follow it. Forcing position:absolute on the
   Gradio options container breaks its native placement logic.
========================================================== */

.control-panel {
    position: relative !important;
    z-index: 20 !important;
    overflow: visible !important;
}

.control-panel > div,
.control-panel .gradio-dropdown,
.control-panel .gradio-dropdown > div {
    overflow: visible !important;
}

.control-panel .gradio-dropdown {
    position: relative !important;
    z-index: 30 !important;
}


/* ==========================================================
   Inputs
========================================================== */

.control-panel input {
    font-size: 16px !important;
}


/* ==========================================================
   Priority queue
========================================================== */

.queue-shell {
    margin-top: 16px;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 20px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.70);
    box-shadow:
        0 16px 48px rgba(15, 23, 42, 0.08);
}

.dark .queue-shell {
    background: rgba(15, 23, 42, 0.66);
}

.queue-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    padding: 20px 22px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.queue-heading {
    font-size: 18px;
    font-weight: 750;
    letter-spacing: -0.02em;
}

.queue-subheading {
    margin-top: 4px;
    color: #64748b;
    font-size: 13px;
}

.queue-count {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    height: 34px;
    padding: 0 12px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.12);
    color: #6366f1;
    font-size: 13px;
    font-weight: 750;
}

.queue-list {
    max-height: 680px;
    overflow-y: auto;
    padding: 8px;
}

.queue-card {
    display: block;
    margin: 5px 0;
    border: 1px solid transparent;
    border-radius: 14px;
    background: rgba(148, 163, 184, 0.055);
    transition:
        background 0.15s ease,
        border-color 0.15s ease,
        transform 0.15s ease;
}

.queue-card:hover {
    border-color: rgba(99, 102, 241, 0.22);
    background: rgba(99, 102, 241, 0.055);
    transform: translateY(-1px);
}

.queue-card[open] {
    border-color: rgba(99, 102, 241, 0.24);
    background: rgba(99, 102, 241, 0.045);
}

.queue-summary {
    display: flex;
    align-items: stretch;
    gap: 16px;
    padding: 16px;
    cursor: pointer;
    list-style: none;
}

.queue-summary::-webkit-details-marker {
    display: none;
}

.queue-summary:focus-visible {
    outline: 2px solid rgba(99, 102, 241, 0.65);
    outline-offset: -2px;
    border-radius: 14px;
}

.queue-expand-hint {
    margin-top: 9px;
    color: #94a3b8;
    font-size: 11px;
    font-weight: 600;
}

.queue-chevron {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 28px;
    width: 28px;
    height: 28px;
    margin-top: 4px;
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 8px;
    color: #64748b;
    font-size: 22px;
    line-height: 1;
    transform: rotate(0deg);
    transition: transform 0.15s ease;
}

.queue-card[open] .queue-chevron {
    transform: rotate(90deg);
}

.queue-details {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin: 0 16px 16px 74px;
    padding: 14px;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.detail-item {
    min-width: 0;
    padding: 10px 11px;
    border-radius: 10px;
    background: rgba(148, 163, 184, 0.07);
}

.detail-label {
    display: block;
    margin-bottom: 4px;
    color: #94a3b8;
    font-size: 10px;
    font-weight: 750;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

.detail-value {
    display: block;
    color: #334155;
    font-size: 13px;
    font-weight: 650;
    overflow-wrap: anywhere;
}

.dark .detail-value {
    color: #e2e8f0;
}

.queue-rank {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 42px;
    width: 42px;
    height: 42px;
    border-radius: 11px;
    background: rgba(100, 116, 139, 0.12);
    color: #64748b;
    font-size: 13px;
    font-weight: 800;
}

.queue-main {
    min-width: 0;
    flex: 1;
}

.queue-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
}

.queue-name {
    min-width: 0;
    color: #0f172a;
    font-size: 16px;
    font-weight: 700;
    overflow-wrap: anywhere;
}

.dark .queue-name {
    color: #f8fafc;
}

.queue-risk {
    flex: 0 0 auto;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.risk-high {
    color: #f87171;
}

.risk-medium {
    color: #fbbf24;
}

.risk-low {
    color: #60a5fa;
}

.queue-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 7px;
    color: #64748b;
    font-size: 12px;
    line-height: 1.5;
}

.meta-separator {
    color: #94a3b8;
}

.risk-track {
    height: 4px;
    margin-top: 12px;
    overflow: hidden;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.14);
}

.risk-fill {
    height: 100%;
    min-width: 2px;
    border-radius: inherit;
    opacity: 0.8;
}


/* ==========================================================
   Search
========================================================== */

.search-panel {
    padding: 20px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.70);
    box-shadow:
        0 12px 38px rgba(15, 23, 42, 0.05);
}

.dark .search-panel {
    background: rgba(15, 23, 42, 0.65);
}

.search-results {
    margin-top: 18px;
    max-height: 600px;
    overflow-y: auto;
}

.search-result-heading {
    margin-bottom: 10px;
    color: #64748b;
    font-size: 13px;
    font-weight: 650;
}

.search-card {
    display: flex;
    gap: 14px;
    padding: 15px;
    margin: 7px 0;
    border: 1px solid rgba(148, 163, 184, 0.17);
    border-radius: 14px;
    background: rgba(148, 163, 184, 0.05);
}

.search-rank {
    flex: 0 0 auto;
    color: #64748b;
    font-size: 13px;
    font-weight: 800;
}

.search-main {
    min-width: 0;
    flex: 1;
}

.search-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
}

.search-name {
    color: #0f172a;
    font-weight: 700;
    overflow-wrap: anywhere;
}

.dark .search-name {
    color: #f8fafc;
}


/* ==========================================================
   Buttons
========================================================== */

button.primary {
    border-radius: 10px !important;
    font-weight: 700 !important;
}


/* ==========================================================
   Footer / informational area
========================================================== */

.info-panel {
    margin-top: 20px;
    padding: 24px;
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 18px;
    background: rgba(248, 250, 252, 0.60);
}

.dark .info-panel {
    background: rgba(15, 23, 42, 0.55);
}


/* ==========================================================
   Mobile
========================================================== */

@media (max-width: 700px) {

    .hero {
        padding: 38px 26px;
        border-radius: 20px;
    }

    .hero p {
        font-size: 15px;
    }

    .control-panel,
    .search-panel {
        padding: 16px;
    }

    .queue-summary {
        gap: 11px;
        padding: 13px;
    }

    .queue-expand-hint {
        font-size: 10px;
    }

    .queue-chevron {
        flex-basis: 24px;
        width: 24px;
        height: 24px;
    }

    .queue-details {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 0 13px 13px 58px;
        padding: 11px 0 0 0;
    }

    .queue-rank {
        flex-basis: 34px;
        width: 34px;
        height: 34px;
    }

    .queue-title-row,
    .search-title-row {
        align-items: flex-start;
    }

    .queue-name,
    .search-name {
        font-size: 14px;
    }

    .queue-risk {
        font-size: 14px;
    }
}
"""


# ============================================================
# Gradio application
# ============================================================

with gr.Blocks(
    title="Restaurant Inspection Prioritization",
) as demo:

    # ========================================================
    # Hero
    # ========================================================

    gr.HTML(
        """
        <section class="hero">

            <div class="hero-content">

                <div class="hero-eyebrow">
                    NYC Inspection Operations
                </div>

                <h1>
                    Know where to inspect first.
                </h1>

                <p>
                    Build a prioritized inspection queue from
                    historical restaurant risk.
                </p>

            </div>

        </section>
        """
    )

    # ========================================================
    # Queue controls
    # ========================================================

    gr.HTML(
        """
        <div class="section-heading">

            <h2>
                Build an inspection queue
            </h2>

            <p>
                Set your inspection capacity and narrow the restaurant population.
            </p>

        </div>
        """
    )

    with gr.Group(
        elem_classes=["control-panel"]
    ):

        with gr.Row():

            capacity = gr.Textbox(
                value="100",
                label="Inspection capacity",
                placeholder="Number of inspections",
                max_length=4,
                lines=1,
                scale=1,
            )

            selected_boroughs = gr.Dropdown(
                choices=BOROUGHS,
                label="Borough",
                value=[],
                multiselect=True,
                interactive=True,
                scale=1,
            )

            selected_cuisines = gr.Dropdown(
                choices=CUISINES,
                label="Cuisine",
                value=[],
                multiselect=True,
                interactive=True,
                scale=2,
            )

        with gr.Row():

            reset_button = gr.Button(
                "Reset filters",
                variant="secondary",
                size="sm",
            )

    # ========================================================
    # Priority queue
    # ========================================================

    gr.HTML(
        """
        <div class="section-heading">

            <h2>
                Priority queue
            </h2>

            <p>
                Highest-ranked restaurants appear first.
                The queue updates when the capacity or filters change.
            </p>

        </div>
        """
    )

    queue_html = gr.HTML(
        value=render_queue(
            "100",
            [],
            [],
        )
    )

    # ========================================================
    # Queue updates
    # ========================================================

    capacity.change(
        fn=render_queue,
        inputs=[
            capacity,
            selected_boroughs,
            selected_cuisines,
        ],
        outputs=queue_html,
    )

    capacity.submit(
        fn=render_queue,
        inputs=[
            capacity,
            selected_boroughs,
            selected_cuisines,
        ],
        outputs=queue_html,
    )

    selected_boroughs.change(
        fn=render_queue,
        inputs=[
            capacity,
            selected_boroughs,
            selected_cuisines,
        ],
        outputs=queue_html,
    )

    selected_cuisines.change(
        fn=render_queue,
        inputs=[
            capacity,
            selected_boroughs,
            selected_cuisines,
        ],
        outputs=queue_html,
    )

    reset_button.click(
        fn=reset_filters,
        inputs=[],
        outputs=[
            capacity,
            selected_boroughs,
            selected_cuisines,
            queue_html,
        ],
    )

    # ========================================================
    # Restaurant search
    # ========================================================

    gr.HTML(
        """
        <div class="section-heading">

            <h2>
                Find a restaurant
            </h2>

            <p>
                Search by restaurant name or CAMIS ID.
            </p>

        </div>
        """
    )

    with gr.Group(
        elem_classes=["search-panel"]
    ):

        with gr.Row():

            search_box = gr.Textbox(
                label="Restaurant or CAMIS",
                placeholder="e.g. 50001215 or restaurant name",
                max_length=MAX_SEARCH_LENGTH,
                lines=1,
                scale=5,
            )

            search_button = gr.Button(
                "Search",
                variant="primary",
                scale=1,
            )

        search_results = gr.HTML()

    search_button.click(
        fn=search_restaurants,
        inputs=search_box,
        outputs=search_results,
    )

    search_box.submit(
        fn=search_restaurants,
        inputs=search_box,
        outputs=search_results,
    )

    # ========================================================
    # Interpretation
    # ========================================================

    gr.HTML(
        """
        <div class="section-heading">
            <h2>
                What the risk means
            </h2>
        </div>

        <div class="info-panel">

            <p>
                The percentage shown for each restaurant is the
                model's calibrated estimated probability of the
                project's defined high-severity outcome at the
                restaurant's next eligible inspection.
            </p>

            <p>
                A higher value places a restaurant earlier in the
                inspection queue.
            </p>

            <p>
                This is a prioritization tool. A high score does not
                mean that a restaurant is currently unsafe, nor does
                it establish that a violation will occur.
            </p>

        </div>
        """
    )

    # ========================================================
    # Footer
    # ========================================================

    gr.Markdown(
        """
---

**Restaurant Inspection Prioritization**

Batch-scored from historical NYC restaurant inspection data.
"""
    )


# ============================================================
# Launch
# ============================================================

if __name__ == "__main__":
    demo.launch(
        css=CSS,
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="slate",
            neutral_hue="slate",
            font=[
                gr.themes.GoogleFont("Inter"),
                "ui-sans-serif",
                "system-ui",
                "sans-serif",
            ],
        ),
    )