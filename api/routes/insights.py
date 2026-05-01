"""Daily Insights REST API — Frontend access to generated insight reports."""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

insights_bp = Blueprint("insights", __name__, url_prefix="/api/insights")

INSIGHTS_DIR = Path("data/insights")


def _list_insights() -> list:
    """List available insight reports sorted by date (newest first)."""
    if not INSIGHTS_DIR.exists():
        return []
    files = []
    for f in INSIGHTS_DIR.glob("*.md"):
        try:
            date_str = f.stem
            datetime.strptime(date_str, "%Y-%m-%d")
            files.append({
                "date": date_str,
                "filename": f.name,
                "size": f.stat().st_size,
            })
        except ValueError:
            continue
    files.sort(key=lambda x: x["date"], reverse=True)
    return files


def _read_insight(date_str: str) -> str | None:
    """Read a specific insight report."""
    path = INSIGHTS_DIR / f"{date_str}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


@insights_bp.route("/daily", methods=["GET"])
def get_daily_insight():
    """Get today's insight report (or a specific date)."""
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    content = _read_insight(date_str)
    if content is None:
        return jsonify({
            "success": True,
            "data": {
                "date": date_str,
                "content": None,
                "generated": False,
                "message": "No insight report found for this date. Run `python scripts/generate_daily_insight.py` to generate.",
            },
        }), 200

    return jsonify({
        "success": True,
        "data": {
            "date": date_str,
            "content": content,
            "generated": True,
        },
    })


@insights_bp.route("/history", methods=["GET"])
def get_insight_history():
    """List all available insight reports."""
    files = _list_insights()
    return jsonify({
        "success": True,
        "data": {
            "reports": files,
            "total": len(files),
        },
    })


@insights_bp.route("/generate", methods=["POST"])
def generate_insight():
    """Trigger daily insight generation on demand."""
    user_id = request.args.get("user_id", "anonymous")
    data = request.get_json() or {}
    use_llm = data.get("use_llm", True)

    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts.generate_daily_insight import generate_daily_insight

        content = generate_daily_insight(
            user_id=user_id,
            output_dir=str(INSIGHTS_DIR),
            use_llm=use_llm,
        )
        return jsonify({
            "success": True,
            "data": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "generated": True,
                "content_preview": content[:500] + "..." if len(content) > 500 else content,
            },
        })
    except Exception as e:
        logger.error("Daily insight generation failed: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Generation failed. Fallback: run `python scripts/generate_daily_insight.py --no-llm` manually.",
        }), 500
