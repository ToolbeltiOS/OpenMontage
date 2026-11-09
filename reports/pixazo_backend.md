# Illustration backend: Pixazo primary, Cloudflare fallback

## The quota is shared, and this pipeline cannot see the other half

Pixazo's free tier is an allowance on the **account**, shared across every
API key on it. The Shorts pipeline in `~/Desktop/wak3up` already calls the
same endpoint with the same key. Two pipelines, one bucket.

The Shorts poster is paused, so today the bucket is effectively ours. That
is a fact about this week, not a property of the system.

| | |
|---|---|
| free allowance | **750 images/month**, resets on the 1st |
| scope | the whole account, all keys |
| rate limit | 60 req/min per API (older Pixazo posts say ~10) |
| price after the allowance | $0.0012/image |

Both published rate figures were found; `lib/pixazo_quota.py` uses the
**lower** one. Being wrong about a rate limit costs a 429 and a retry;
being wrong cautiously costs nothing.

**Refusal at 80%**, as instructed: 600 images/month, and calls spaced for 8
req/min. `reports/pixazo_usage.json` counts what OpenMontage spent — and
every report it prints says that number is an **undercount**, because the
Shorts pipeline's usage is not visible from this machine.

## Is it free or $0.0012?

Both, and the Shorts code and the vendor page are not in conflict. The
Shorts comment reads "Primary: Pixazo ($0.0012/image)", which is the rate
**after** the free allowance; Pixazo's free-tier page grants 750 images a
month before that applies. The free tier also activates only once the wallet
has been topped up at least once.

## The two clients differ in shape

Not interchangeable, and treating them as such is how a fallback silently
returns nothing:

| | Pixazo | Cloudflare Workers AI |
|---|---|---|
| auth | `Ocp-Apim-Subscription-Key` (Azure APIM) | `Authorization: Bearer` |
| steps field | `num_steps` | `steps` |
| returns | a URL to fetch | base64 inside a JSON envelope |

Neither endpoint takes a negative prompt, so the house negative is appended
to the prompt text as a clause rather than dropped — dropping it would leave
an illustration free to come back photorealistic, which is the one thing the
style exists to prevent.

## Blocked: the key is not on this machine

`PIXAZO_API_KEY` is **absent**. There is no `.env` in `~/wak3up` or
`~/Desktop/wak3up`, and the Shorts code loads it from `~/wak3up/.env`, which
does not exist locally — the Shorts pipeline runs on the droplet, so the key
lives there. Nothing could be copied. The backend is built and refuses
cleanly with "PIXAZO_API_KEY is not set".
