# My agent: Habit Pulse (Daily Habit & Wellness Companion)

One-liner: A conversational agent that helps individuals track, build, and maintain daily habits (fitness, reading, mindfulness) with a personal habit dashboard, streak tracking, and custom milestone badges.

Tool coverage:
- Memory: User's active habits, target goals (e.g. 2L water daily, 10m meditation), streak records, completion history, and personal wellness preferences across sessions.
- Tools: `log_habit(habit_name, amount, unit)`, `get_daily_summary()`, `create_habit(name, target, frequency)`, `get_streak_analytics()`.
- Catalog/UI: Daily habit checklist table, streak progress card, and weekly completion stats.
- Image gen: Generates milestone achievement badges (e.g., "7-Day Mindfulness Streak Badge" or "Hydro Master Medal").
- Sandbox: Computes weekly habit consistency percentages, streak statistics, and goal progress metrics.

Core rails (everyone): memory, tools, eval, deploy, frontend
My stretch menu (pick later): A2UI habit dashboard cards, milestone badge image generation, code sandbox analytics.
First eval question: User says: "I drank 2L of water and meditated for 10 minutes." -> Expected Response: Logs both habits, acknowledges the 5-day meditation streak, displays an updated daily progress card, and offers a brief motivational encouragement.
