# NenekBot Vercel Proxy

This folder is a tiny Vercel project that proxies all traffic from a Vercel custom domain to the existing Render backend:

```text
https://nenekbot.onrender.com
```

Use this when the Render custom-domain quota is full but the Flask app should keep running on Render.

## Vercel Import Settings

When importing the GitHub repository into Vercel, use:

| Setting | Value |
| --- | --- |
| Framework Preset | Other |
| Root Directory | `vercel-proxy` |
| Build Command | Leave empty |
| Output Directory | Leave empty |
| Install Command | Leave empty |

Then add the custom domain:

```text
nenekbot.yazidzqwn.com
```

In Spaceship DNS, create:

| Type | Host | Value |
| --- | --- | --- |
| CNAME | `nenekbot` | `cname.vercel-dns-0.com` |

If Vercel shows a different CNAME value, use the value shown by Vercel.
