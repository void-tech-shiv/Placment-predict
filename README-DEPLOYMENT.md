# Deployment Architecture

Placement Predict is deployed with a two-platform setup:

- **Render** hosts the actual Flask + ML application on the free web-service tier.
- **Vercel** acts as the public edge proxy/front door and forwards all application routes to the Render service while keeping the Vercel hostname in the browser.

This split keeps the long-running Python/ML workload on Render and avoids Vercel serverless filesystem/runtime limitations for mutable app state and model training.

Render service URL:

`https://placement-predict-0vnt.onrender.com`

The Vercel proxy is configured in `vercel.json`.

## Production notes

- Render free services can sleep when idle and may take time to wake on the first request.
- Runtime files on the free service are not a replacement for a persistent database or disk.
- The first registered account becomes Administrator when there are no existing runtime users.
- For a long-lived production deployment, set a strong `SECRET_KEY` in Render environment variables and move users/history to a persistent database.
