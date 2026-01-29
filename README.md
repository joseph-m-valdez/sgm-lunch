# SGM Lunch Menu

Automated school lunch menu scraper that publishes JSON files to GitHub Pages for easy Siri Shortcut integration.

## Setup

### 1. Get a Gemini API Key (Free)

1. Go to https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key

### 2. Add GitHub Secret

In your repo: Settings > Secrets and variables > Actions > New repository secret

- `GEMINI_API_KEY`: Your Gemini API key (required)

### 3. Enable GitHub Pages

1. Go to Settings > Pages
2. Source: "Deploy from a branch"
3. Branch: `main`, folder: `/ (root)`
4. Save

Your data will be available at:
```
https://<username>.github.io/sgm-lunch/data/2026-01.json
```

### 4. Run the Workflow

1. Go to Actions > "Update Lunch Menu"
2. Click "Run workflow"
3. Check that `data/YYYY-MM.json` was created

## Local Development

```bash
# Install dependencies
uv sync

# Install Playwright browser (first time only)
uv run playwright install chromium

# Run the updater
GEMINI_API_KEY="your-key" uv run python scripts/update_menu.py
```

The script uses Playwright to bypass Cloudflare protection and automatically finds the menu calendar image.

## Tests

```bash
uv run pytest
```

## Siri Shortcut Setup

Create a new Shortcut with these steps:

1. **Get Current Date** (or ask for input date)
2. **Format Date** as `yyyy-MM` → save to variable `monthKey`
3. **Format Date** as `yyyy-MM-dd` → save to variable `dayKey`
4. **Get Contents of URL**: `https://<username>.github.io/sgm-lunch/data/[monthKey].json`
5. **Get Dictionary Value** for key `[dayKey]`
6. **If** result has any value:
   - **Speak Text**: "Today's lunch is [result]"
7. **Otherwise**:
   - **Speak Text**: "No lunch listed for that date"

### Quick Setup (Import Link)

After you've published at least one menu, I can help you generate a shareable Shortcut link.

## Schedule

The workflow runs automatically:
- Days 1-7 of each month: Twice daily (8am & 8pm UTC)
- Days 8-28: Once daily (8am UTC)

This handles late calendar updates at the start of each month.

## Data Format

Each `data/YYYY-MM.json` file contains:

```json
{
  "2026-01-06": "Pizza with salad",
  "2026-01-07": "Chicken nuggets",
  "2026-01-20": "NO SCHOOL",
  "2026-01-21": null
}
```

- Keys: ISO date format (`YYYY-MM-DD`)
- Values: Lunch description, "NO SCHOOL", or `null` if unclear
