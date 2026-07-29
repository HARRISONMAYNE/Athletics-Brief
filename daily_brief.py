name: Daily Athletics Brief

on:
  schedule:
    # 05:30 UTC = 06:30 BST. GitHub's scheduler can run a few minutes late.
    - cron: "30 5 * * *"
  workflow_dispatch: # lets you trigger a run by hand from the Actions tab

permissions:
  contents: write

jobs:
  brief:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install feedparser pyyaml anthropic

      - name: Build and send the brief
        env:
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          MAIL_FROM: ${{ secrets.MAIL_FROM }}
          MAIL_TO: ${{ secrets.MAIL_TO }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python daily_brief.py

      - name: Publish to the site
        run: |
          git config user.name "athletics-brief-bot"
          git config user.email "actions@github.com"
          git add docs/
          git diff --staged --quiet || git commit -m "Brief: $(date -u +%Y-%m-%d)"
          git push
