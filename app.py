from pathlib import Path
import json
import re

import pandas as pd
import plotly.express as px
import streamlit as st

# PLAYER_SENTIMENT_UPGRADE
from src.insights import detect_players, estimate_sentiment, PLAYERS

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Cricket Fan Insights",
    page_icon="🏏",
    layout="wide",
)

TOPICS = {
    "Batting": [
        "batting", "batsman", "batter", "century", "hundred",
        "six", "sixes", "boundary", "boundaries", "بلے بازی",
    ],
    "Bowling": [
        "bowling", "bowler", "wicket", "wickets", " yorker",
        "pace", "spinner", "spin", "باؤلنگ", "وکٹ",
    ],
    "Fielding": [
        "fielding", "fielder", "catch", "catches",
        "run out", "runout", "فیلڈنگ", "کیچ",
    ],
    "Selection and captaincy": [
        "captain", "captaincy", "selection", "selector",
        "squad", "کپتان", "سلیکشن",
    ],
    "Umpiring": [
        "umpire", "umpiring", "drs", "no ball",
        "noball", "امپائر",
    ],
    "Video and coverage": [
        "highlights", "commentary", "commentator",
        "camera", "editing", "audio", "coverage", "کمنٹری",
    ],
}

PATTERNS = {
    topic: re.compile(
        r"(?<!\w)(?:"
        + "|".join(re.escape(word.strip()) for word in words)
        + r")(?!\w)",
        flags=re.IGNORECASE,
    )
    for topic, words in TOPICS.items()
}


def label_topics(text):
    matches = [
        topic for topic, pattern in PATTERNS.items()
        if pattern.search(str(text))
    ]
    return matches or ["Unclassified"]


def safe_csv(frame):
    result = frame.copy()
    # Prevent comment text being interpreted as spreadsheet formulas.
    for column in result.select_dtypes(include=["object", "string"]).columns:
        result[column] = result[column].map(
            lambda value: "'" + value
            if isinstance(value, str)
            and value.lstrip().startswith(("=", "+", "-", "@"))
            else value
        )
    return result.to_csv(index=False).encode("utf-8-sig")


st.title("🏏 Cricket Fan Insights")
st.write("Explore audience discussions in a collected sample of cricket videos.")
st.caption(
    "Business question: What cricket topics could a sports channel "
    "explore in its next content?"
)

path = ROOT / "data" / "processed" / "clean_comments.csv"
if not path.exists():
    st.error("Clean dataset missing. Run: python src/clean_data.py")
    st.stop()

df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
required = {"video_id", "comment_id", "clean_text", "like_count"}
if not required.issubset(df.columns):
    st.error("Dataset columns do not match the expected cleaned format.")
    st.stop()

df["clean_text"] = df["clean_text"].astype(str)
df["video_id"] = df["video_id"].astype(str)
df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce")
df["topic_list"] = df["clean_text"].map(label_topics)
df["topics"] = df["topic_list"].map(lambda items: ", ".join(items))
df["player_list"] = df["clean_text"].map(detect_players)
df["players"] = df["player_list"].map(
    lambda items: ", ".join(items) if items else "No configured player matched"
)
sentiment_results = pd.DataFrame(
    df["clean_text"].map(estimate_sentiment).tolist(), index=df.index
)
df = pd.concat([df, sentiment_results], axis=1)

st.sidebar.header("Explore comments")
selected_videos = st.sidebar.multiselect(
    "Videos",
    options=sorted(df["video_id"].unique()),
    default=sorted(df["video_id"].unique()),
)
search = st.sidebar.text_input("Search comments", placeholder="e.g. Babar")
selected_topic = st.sidebar.selectbox(
    "Topic", ["All topics"] + list(TOPICS) + ["Unclassified"]
)

selected_player = st.sidebar.selectbox(
    "Player mentioned", ["All players"] + list(PLAYERS)
)
selected_sentiment = st.sidebar.selectbox(
    "Estimated sentiment",
    ["All sentiments", "Positive", "Negative", "Mixed", "Neutral / unclear"]
)
exact_search = st.sidebar.checkbox("Match whole words / phrase", value=False)
review_only = st.sidebar.checkbox("Only comments suggested for review")

view = df[df["video_id"].isin(selected_videos)].copy()
if selected_player != "All players":
    view = view[
        view["player_list"].map(lambda names: selected_player in names)
    ]
if selected_sentiment != "All sentiments":
    view = view[view["sentiment"] == selected_sentiment]
if review_only:
    view = view[view["review_suggested"]]
if search.strip():
    view = view[
        view["clean_text"].str.contains(
            (
                r"(?<!\w)" + re.escape(search.strip()) + r"(?!\w)"
                if exact_search else search.strip()
            ),
            case=False, regex=exact_search, na=False
        )
    ]
if selected_topic != "All topics":
    view = view[
        view["topic_list"].map(lambda items: selected_topic in items)
    ]

st.sidebar.caption(
    "Topics use English and selected Urdu keywords. "
    "Roman Urdu, spelling variations and context may be missed."
)

a, b, c, d = st.columns(4)
a.metric("Comments in dataset", f"{len(df):,}")
b.metric("Filtered comments", f"{len(view):,}")
c.metric("Selected videos with data", view["video_id"].nunique())
average = view["like_count"].mean()
d.metric("Mean likes per comment", f"{average:.1f}" if pd.notna(average) else "N/A")

overview, explorer, reactions, quality = st.tabs(
    ["Overview", "Comment explorer", "Players and sentiment",
     "Data quality and method"]
)

with overview:
    if view.empty:
        st.info("No comments match these filters. Change your selection.")
    else:
        counts = (
            view.groupby("video_id").size()
            .rename("comments").reset_index()
        )
        st.plotly_chart(
            px.bar(
                counts, x="video_id", y="comments",
                title="Collected comments by video — filtered sample",
                labels={"video_id": "Video", "comments": "Comments"},
                color_discrete_sequence=["#16a085"],
            ),
            use_container_width=True,
        )
        st.caption(
            "These counts reflect collection limits, not each video's "
            "total popularity or total comments."
        )

        expanded = view[["comment_id", "video_id", "topic_list"]].explode(
            "topic_list"
        )
        summary = (
            expanded.groupby("topic_list").size()
            .rename("comments").reset_index()
            .rename(columns={"topic_list": "topic"})
        )
        summary["percentage"] = 100 * summary["comments"] / len(view)

        st.plotly_chart(
            px.bar(
                summary.sort_values("percentage"),
                x="percentage", y="topic", orientation="h",
                title="Share of filtered comments matching each topic",
                labels={"percentage": "Comments (%)", "topic": "Topic"},
                hover_data=["comments"],
                color_discrete_sequence=["#2563eb"],
            ),
            use_container_width=True,
        )
        st.caption(
            "One comment can match multiple topics, so percentages may "
            "exceed 100% when added. Unclassified does not mean neutral."
        )

        comparison = (
            expanded.groupby(["video_id", "topic_list"]).size()
            .rename("matches").reset_index()
        )
        denominators = view.groupby("video_id").size()
        comparison["percentage"] = (
            comparison["matches"]
            / comparison["video_id"].map(denominators) * 100
        )
        matrix = comparison.pivot(
            index="topic_list", columns="video_id", values="percentage"
        ).fillna(0)
        st.plotly_chart(
            px.imshow(
                matrix, aspect="auto", zmin=0, zmax=100,
                color_continuous_scale="Blues",
                labels={
                    "x": "Video", "y": "Topic",
                    "color": "Comments (%)",
                },
                title="Topic percentages within each video's filtered sample",
            ),
            use_container_width=True,
        )

        st.subheader("Content idea to investigate")
        classified = summary[summary["topic"] != "Unclassified"]
        ideas = {
            "Batting": "a batting technique or innings breakdown",
            "Bowling": "a bowling strategy or wicket analysis",
            "Fielding": "a fielding and catching analysis",
            "Selection and captaincy": "a team selection and captaincy discussion",
            "Umpiring": "an explanation of umpiring decisions and rules",
            "Video and coverage": "a review of viewer feedback on video coverage",
        }
        if classified.empty:
            st.info("No topic keywords matched. Review comments manually.")
        else:
            top = classified.sort_values(
                ["comments", "topic"], ascending=[False, True]
            ).iloc[0]
            st.write(
                f"{top['topic']} matched {int(top['comments'])} of "
                f"{len(view)} filtered comments ({top['percentage']:.1f}%). "
                f"Consider testing {ideas[top['topic']]}."
            )
            st.caption(
                "This is a keyword-based suggestion, not proof of demand "
                "or positive sentiment. Read matching comments before deciding."
            )

with explorer:
    st.subheader("Comments, ordered by likes")
    display_columns = [
        column for column in [
            "video_id", "clean_text", "topics", "players", "sentiment",
            "sentiment_evidence", "review_suggested", "like_count",
            "reply_count", "published_at", "video_url",
        ] if column in view.columns
    ]
    display = view.sort_values(
        "like_count", ascending=False, na_position="last"
    )[display_columns]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered comments",
        data=safe_csv(display),
        file_name="filtered_cricket_comments.csv",
        mime="text/csv",
    )
    st.caption(
        "Downloads prefix formula-like text with an apostrophe "
        "for safer opening in spreadsheet software."
    )

with reactions:
    st.subheader("Estimated comment sentiment")
    st.warning(
        "Experimental keyword estimates, not validated AI predictions. "
        "Neutral / unclear includes opinions the rules miss. "
        "Sarcasm and mixed-language comments need manual review."
    )
    if view.empty:
        st.info("No comments match the current filters.")
    else:
        sentiment_counts = (
            view.groupby("sentiment").size()
            .rename("comments").reset_index()
        )
        sentiment_counts["percentage"] = (
            sentiment_counts["comments"] / len(view) * 100
        )
        st.plotly_chart(
            px.bar(
                sentiment_counts, x="sentiment", y="comments",
                color="sentiment", hover_data=["percentage"],
                color_discrete_map={
                    "Positive": "#16a34a",
                    "Negative": "#dc2626",
                    "Mixed": "#d97706",
                    "Neutral / unclear": "#64748b",
                },
                title="Sentiment estimates in the filtered sample",
            ),
            use_container_width=True,
        )
        st.dataframe(
            sentiment_counts, hide_index=True, use_container_width=True
        )

        st.subheader("Player mentions")
        mentioned = view[view["player_list"].map(bool)].explode("player_list")
        if mentioned.empty:
            st.info("No configured player names matched.")
        else:
            player_counts = (
                mentioned.groupby("player_list").size()
                .rename("comments").reset_index()
                .rename(columns={"player_list": "player"})
                .sort_values("comments", ascending=False)
            )
            st.plotly_chart(
                px.bar(
                    player_counts, x="player", y="comments",
                    title="Comments mentioning each configured player",
                    color_discrete_sequence=["#0891b2"],
                ),
                use_container_width=True,
            )

        st.caption(
            "A comment can mention multiple players. Mentions do not mean "
            "praise. Sentiment describes the whole comment, not a specific "
            "player. The player dictionary is not exhaustive."
        )
        st.metric(
            "Comments suggested for manual review",
            int(view["review_suggested"].sum()),
        )
        st.caption(
            "The review flag is a heuristic, not a confidence score. "
            "Unflagged predictions can also be wrong."
        )
        st.download_button(
            "Download sentiment summary",
            data=safe_csv(sentiment_counts),
            file_name="sentiment_summary.csv",
            mime="text/csv",
        )

with quality:
    st.subheader("Cleaning report")
    report_path = ROOT / "reports" / "cleaning_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            st.json(report)
        except (ValueError, OSError):
            st.warning("Could not read the cleaning report.")

    st.subheader("How to interpret the results")
    st.write(
        "- The dataset contains recent top-level comments from selected videos.\n"
        "- Replies were excluded; reply_count only records their number.\n"
        "- The active dataset may combine multiple collection runs. See the cleaning report for current counts per video.\n"
        "- Percentages account for different sample sizes but do not remove "
        "selection bias or the greater uncertainty of smaller samples.\n"
        "- Duplicate IDs and blank comments were checked. Repeated phrases, "
        "emojis and non-English comments were retained.\n"
        "- Keyword labels are approximate, multi-label topic tags, not AI "
        "sentiment predictions. Separate sentiment estimates use opinion keywords.\n"
        "- Comment likes are a snapshot at collection time.\n"
        "- These viewers do not represent all cricket fans."
    )
    with st.expander("View the topic keyword rules"):
        st.json(TOPICS)

st.divider()
st.caption("Cricket Fan Insights | Python · Pandas · Streamlit · Plotly")
