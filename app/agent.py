# ruff: noqa
import datetime
from typing import Any
from google.cloud import firestore

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from .a2ui_utils import a2ui_callback

# CRITICAL: Hardcode GCP Project ID as string (do NOT read from auth/env on Agent Platform)
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-4891f3ba97eb"
COLLECTION_NAME = "habit_entries"

_db = None


def get_db() -> firestore.Client:
    """Lazy initializer for Firestore Client to ensure clean deployment serialization."""
    global _db
    if _db is None:
        _db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    return _db


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except (ValueError, AttributeError):
        pass
    return None


def _calculate_streak(history: dict[str, float], target: float) -> int:
    """Calculates consecutive days completed from history."""
    completed_dates = set()
    for dt, val in history.items():
        if val >= target:
            completed_dates.add(dt)

    if not completed_dates:
        return 0

    iso_dates = []
    for d in completed_dates:
        try:
            iso_dates.append(datetime.date.fromisoformat(d))
        except ValueError:
            pass

    if iso_dates:
        iso_dates.sort(reverse=True)
        streak = 1
        for i in range(len(iso_dates) - 1):
            if (iso_dates[i] - iso_dates[i + 1]).days == 1:
                streak += 1
            else:
                break
        return streak

    return len(completed_dates)


def _get_habit_history(habit_name: str) -> tuple[dict[str, float], float, str]:
    """Queries Firestore collection 'habit_entries' for a habit's history."""
    key = habit_name.lower().strip()
    db = get_db()
    docs = (
        db.collection(COLLECTION_NAME)
        .where("habit_name", "==", key)
        .stream()
    )

    history = {}
    target = 0.0
    unit = ""

    for doc in docs:
        data = doc.to_dict()
        d_str = data.get("date", "")
        amt = float(data.get("amount", 0.0))
        if d_str:
            history[d_str] = history.get(d_str, 0.0) + amt
        if "target" in data and data["target"]:
            target = float(data["target"])
        if "unit" in data and data["unit"]:
            unit = data["unit"]

    if target == 0.0:
        # Fallback default targets
        defaults = {"water": (2.0, "L"), "meditation": (10.0, "mins"), "reading": (20.0, "pages")}
        target, unit = defaults.get(key, (1.0, "times"))

    return history, target, unit


def log_habit(
    habit_name: str, amount: float, unit: str, date_str: str = ""
) -> str:
    """Logs completion or progress for a habit for a specific date or today in Firestore.

    Args:
        habit_name: Name of the habit (e.g., 'water', 'meditation', 'reading').
        amount: Numerical value logged (e.g., 2.0, 10.0, 30.0).
        unit: Unit of measurement (e.g., 'L', 'mins', 'pages').
        date_str: Optional target date in YYYY-MM-DD format, or 'yesterday'. Defaults to today.

    Returns:
        Confirmation string with date, updated status, and calculated streak from Firestore.
    """
    if not date_str or date_str.lower() in ("today", "now"):
        target_date = datetime.date.today().isoformat()
    elif date_str.lower() == "yesterday":
        target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    else:
        target_date = date_str.strip()

    key = habit_name.lower().strip()
    doc_id = f"{key}_{target_date}"
    db = get_db()
    doc_ref = db.collection(COLLECTION_NAME).document(doc_id)

    doc = doc_ref.get()
    existing_amount = 0.0
    target_val = amount

    if doc.exists:
        data = doc.to_dict()
        existing_amount = float(data.get("amount", 0.0))
        target_val = float(data.get("target", amount))

    new_total = existing_amount + amount
    status = "Completed" if new_total >= target_val else "In Progress"

    doc_ref.set(
        {
            "habit_name": key,
            "amount": new_total,
            "target": target_val,
            "unit": unit,
            "date": target_date,
            "status": status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        merge=True,
    )

    # Compute streak from Firestore history
    history, target, _ = _get_habit_history(key)
    history[target_date] = new_total
    streak = _calculate_streak(history, target)

    return (
        f"Logged {amount} {unit} for '{habit_name}' on {target_date} in Firestore. "
        f"Total for {target_date}: {new_total}/{target_val} {unit} [{status}]. "
        f"Current streak: {streak} day(s)!"
    )


def get_daily_summary(date_str: str = "") -> str:
    """Retrieves habit progress summary for a specific date (or today) from Firestore.

    Args:
        date_str: Optional target date in YYYY-MM-DD format (defaults to today).

    Returns:
        Formatted summary of habit progress for the specified date from Firestore.
    """
    if not date_str or date_str.lower() in ("today", "now"):
        target_date = datetime.date.today().isoformat()
    elif date_str.lower() == "yesterday":
        target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    else:
        target_date = date_str.strip()

    db = get_db()
    docs = (
        db.collection(COLLECTION_NAME)
        .where("date", "==", target_date)
        .stream()
    )

    lines = [f"Firestore Habit Dashboard for {target_date}:"]
    found_any = False
    for doc in docs:
        found_any = True
        data = doc.to_dict()
        h_name = data.get("habit_name", "").capitalize()
        amt = data.get("amount", 0.0)
        target = data.get("target", 0.0)
        unit = data.get("unit", "")
        status = data.get("status", "In Progress")
        history, t_val, _ = _get_habit_history(data.get("habit_name", ""))
        streak = _calculate_streak(history, t_val)
        lines.append(f"- {h_name}: {amt}/{target} {unit} [{status}] | Streak: {streak} days")

    if not found_any:
        lines.append("No habit records logged in Firestore for this date yet.")

    return "\n".join(lines)


def get_weekly_dashboard() -> str:
    """Generates a full 7-day habit tracking matrix from Firestore records.

    Returns:
        Formatted multi-day overview table from Firestore.
    """
    today = datetime.date.today()
    dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]

    db = get_db()
    # Fetch all habit docs from Firestore
    all_docs = db.collection(COLLECTION_NAME).stream()
    habits_data: dict[str, dict[str, Any]] = {}

    for doc in all_docs:
        data = doc.to_dict()
        key = data.get("habit_name", "").lower()
        if not key:
            continue
        if key not in habits_data:
            habits_data[key] = {"target": float(data.get("target", 1.0)), "history": {}}
        d_str = data.get("date", "")
        amt = float(data.get("amount", 0.0))
        if d_str:
            habits_data[key]["history"][d_str] = amt

    if not habits_data:
        return "No habit records found in Firestore."

    lines = ["📅 7-Day Weekly Habit Matrix (Firestore Backend):"]
    header = f"{'Habit':<12} | " + " | ".join([d[5:] for d in dates]) + " | Streak"
    lines.append(header)
    lines.append("-" * len(header))

    for habit, data in habits_data.items():
        row = f"{habit.capitalize():<12} | "
        target = data["target"]
        history = data["history"]
        for d in dates:
            val = history.get(d, 0.0)
            mark = "✅" if val >= target else (f"{val:.0f}" if val > 0 else "❌")
            row += f"{mark:^7} | "
        streak = _calculate_streak(history, target)
        row += f" {streak}d"
        lines.append(row)

    return "\n".join(lines)


def create_habit(name: str, target: float, unit: str, frequency: str = "daily") -> str:
    """Creates a new habit target entry in Firestore.

    Args:
        name: Name of the habit.
        target: Target numerical goal.
        unit: Unit of measurement (e.g., 'mins', 'pages', 'L', 'steps').
        frequency: Goal frequency (default 'daily').

    Returns:
        Confirmation message.
    """
    key = name.lower().strip()
    today_str = datetime.date.today().isoformat()
    doc_id = f"{key}_{today_str}"
    db = get_db()
    db.collection(COLLECTION_NAME).document(doc_id).set(
        {
            "habit_name": key,
            "amount": 0.0,
            "target": target,
            "unit": unit,
            "date": today_str,
            "status": "In Progress",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        merge=True,
    )
    return f"Created new {frequency} habit '{name}' with target {target} {unit} in Firestore."


def get_streak_analytics(habit_name: str) -> str:
    """Calculates streak consistency statistics for a habit from Firestore history.

    Args:
        habit_name: Name of the habit to calculate statistics for.

    Returns:
        Analytics overview string from Firestore.
    """
    key = habit_name.lower().strip()
    history, target, unit = _get_habit_history(key)
    if history:
        streak = _calculate_streak(history, target)
        completed_days = len([v for v in history.values() if v >= target])
        return (
            f"Firestore Analytics for '{habit_name}': Current streak is {streak} days. "
            f"Total completed days in database: {completed_days}."
        )
    return f"No Firestore history found for habit '{habit_name}'."


def export_habit_report_to_gcs() -> str:
    """Exports all Firestore habit tracking records to a CSV file in public Cloud Storage.

    Returns:
        Public download URL for the exported CSV habit report.
    """
    import csv
    import io
    from google.cloud import storage

    db = get_db()
    docs = db.collection(COLLECTION_NAME).stream()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Habit Name", "Amount", "Target", "Unit", "Status"])

    count = 0
    for doc in docs:
        count += 1
        data = doc.to_dict()
        writer.writerow([
            data.get("date", ""),
            data.get("habit_name", ""),
            data.get("amount", 0.0),
            data.get("target", 0.0),
            data.get("unit", ""),
            data.get("status", "In Progress"),
        ])

    bucket_name = "habit-pulse-assets-qwiklabs-gcp-01-4891f3ba97eb"
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("habit_report.csv")
    blob.upload_from_string(output.getvalue(), content_type="text/csv")

    public_url = f"https://storage.googleapis.com/{bucket_name}/habit_report.csv"
    return f"Exported {count} habit records to Cloud Storage. Download report: {public_url}"


def fetch_daily_wellness_quote() -> str:
    """Fetches a real daily motivational wellness quote from the public ZenQuotes API.

    Returns:
        A daily inspirational quote and author.
    """
    import json
    import os
    import urllib.request

    api_key = os.getenv("ZENQUOTES_API_KEY", "")
    url = "https://zenquotes.io/api/random"
    if api_key:
        url += f"/{api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HabitPulse/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if isinstance(data, list) and len(data) > 0:
                quote = data[0].get("q", "").strip()
                author = data[0].get("a", "Unknown").strip()
                return f'Daily Motivation: "{quote}" — {author}'
    except Exception:
        pass
    return 'Daily Motivation: "Small daily improvements over time lead to stunning results." — Robin Sharma'


RAG_CORPUS_NAME = "projects/23053264641/locations/us-central1/ragCorpora/633274717133864960"


def consult_herbal_knowledge(query: str) -> str:
    """Searches the Culpeper's Complete Herbal knowledge base and returns relevant herbal remedies, plant properties, and wellness facts.

    Args:
        query: What to look up (e.g., an herb, plant, remedy, or health condition).
    Returns:
        Relevant herbal knowledge passages or a note if no match was found.
    """
    import vertexai
    from vertexai.preview import rag

    vertexai.init(project=FIRESTORE_PROJECT_ID, location="us-central1")
    try:
        resp = rag.retrieval_query(
            text=query,
            rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_NAME)],
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=5),
        )
    except Exception as e:
        return f"Herbal knowledge lookup failed: {e}"

    contexts = getattr(resp.contexts, "contexts", [])
    passages = [c.text.strip() for c in contexts if getattr(c, "text", "").strip()]
    return "\n\n---\n\n".join(passages) or "No relevant herbal passages found."


GCS_BUCKET_NAME = "habit-pulse-assets-qwiklabs-gcp-01-4891f3ba97eb"


def generate_habit_badge_image(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates a visual habit badge, milestone icon, or celebration card using the gemini-3.1-flash-lite-image model in the global region.
    Saves the generated image as an artifact via tool_context, uploads the bytes directly to public Cloud Storage, and returns the public https URL.

    Args:
        prompt: Description of the habit badge, milestone icon, or celebration card to generate.
        tool_context: ADK ToolContext for artifact persistence.
    Returns:
        The public Cloud Storage https URL of the generated image.
    """
    from google import genai
    from google.genai import types
    from google.cloud import storage
    import uuid

    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    try:
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )
    except Exception as e:
        return f"Image generation error: {e}"

    image_bytes = None
    mime_type = "image/png"
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return "Failed to generate badge image: No image data returned by model."

    ext = "jpg" if "jpeg" in mime_type else "png"
    filename = f"habit_badge_{uuid.uuid4().hex[:8]}.{ext}"

    # 1. Save with tool_context.save_artifact for Playground Artifacts panel
    try:
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)
    except Exception:
        pass

    # 2. Upload image bytes to public Cloud Storage bucket and return public https URL
    try:
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"badges/{filename}")
        blob.upload_from_string(image_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/badges/{filename}"
    except Exception as e:
        return f"Image generated, but GCS upload failed: {e}"


REASONING_ENGINE_RESOURCE_NAME = (
    "projects/23053264641/locations/us-east1/reasoningEngines/2359369434277085184"
)

sandbox_code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=REASONING_ENGINE_RESOURCE_NAME
)

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="You are Habit Pulse, a friendly daily habit and wellness companion backed by a Firestore database, a Vertex AI RAG Corpus, and Python Code Execution capabilities.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "IMAGE GENERATION DIRECTIVES:\n"
        "- You HAVE image generation capabilities via your `generate_habit_badge_image(prompt)` tool!\n"
        "- NEVER say you cannot generate images. When users ask for a badge, milestone icon, achievement image, or visual card, ALWAYS call `generate_habit_badge_image(prompt)`.\n\n"
        "DATABASE & TRACKING DIRECTIVES:\n"
        "1. All user habit progress, target goals, and dates are persisted in the Firestore `habit_entries` collection.\n"
        "2. When users log habits, call `log_habit` to store records in Firestore.\n"
        "3. When users ask for summaries or weekly stats, call `get_daily_summary` or `get_weekly_dashboard` to read from Firestore.\n"
        "4. When users ask to export, download, or back up their habit data/reports, call `export_habit_report_to_gcs()`.\n"
        "5. When users ask for daily motivation, inspiration, or a daily quote, call `fetch_daily_wellness_quote()`.\n"
        "6. When users ask about herbal remedies, plants, natural health tips, or Culpeper's Herbal, call `consult_herbal_knowledge(query)` to search the RAG Corpus.\n"
        "7. When users ask for a badge, milestone image, or visual card, call `generate_habit_badge_image(prompt)`.\n"
        "8. PreloadMemoryTool loads cross-session facts, complementing the Firestore backend database."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        log_habit,
        get_daily_summary,
        get_weekly_dashboard,
        create_habit,
        get_streak_analytics,
        export_habit_report_to_gcs,
        fetch_daily_wellness_quote,
        consult_herbal_knowledge,
        generate_habit_badge_image,
    ],
    code_executor=sandbox_code_executor,
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
