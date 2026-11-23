# AIC Newsletter — The Monday Drop (Fully Automated)

Interactive 3D weekly AI & tech newsletter with automated weekly curation (via Gemini 4 Hydrogen), GitHub Pages deployment, and GroupMe Bot posting.

## Setup
1. **Enable GitHub Pages:** Go to **Settings → Pages**, set **Source** to **Deploy from a branch**, select `main` / `/ (root)`, and save.
2. **Add Secrets:** Go to **Settings → Secrets and variables → Actions → Secrets** and add:
   - `GROUPME_BOT_ID`: Your GroupMe Bot ID from https://dev.groupme.com/bots
   - `GEMINI_API_KEY`: Your free Google AI Studio API key from https://aistudio.google.com/apikey
3. **Add Variable (optional):** Under **Variables**, add `NEWSLETTER_URL` set to `https://404-not-foundries.github.io/AIC_Newsletter/`.
4. **Test It:** Open the **Actions** tab, select **Weekly GroupMe Newsletter Drop**, and click **Run workflow**.
